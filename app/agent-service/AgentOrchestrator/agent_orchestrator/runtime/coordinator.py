from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ..api.models import (
    AgentStatusEntry,
    ChartConfig,
    DashboardResponse,
    MetricSummary,
    StatusResponse,
    UploadMetadata,
    UploadSession,
)
from ..workflows import UploadToDashboardWorkflow, WorkflowEventRecord, WorkflowExecution, WorkflowResult
from .dashboard_renderer import DashboardRenderer, RenderedDashboard
from .models import (
    AgentStepSnapshot,
    ChartConfigPayload,
    DashboardArtifacts,
    MetricSummaryPayload,
    SessionRecord,
    UploadMetadataPayload,
)
from .persistence import PersistenceManager
from .session_store import SessionNotFoundError, SessionStore

logger = logging.getLogger(__name__)


class DashboardNotReadyError(RuntimeError):
    """Raised when the dashboard endpoint is queried before artifacts exist."""


class SessionCoordinator:
    """Coordinates dataset uploads, workflow execution, and status aggregation."""

    def __init__(
        self,
        store: SessionStore,
        *,
        upload_root: Path | None = None,
        persistence: PersistenceManager | None = None,
    ) -> None:
        self._store = store
        self._upload_root = upload_root or Path(tempfile.gettempdir()) / "agent-orchestrator" / "uploads"
        self._upload_root.mkdir(parents=True, exist_ok=True)
        self._workflow = UploadToDashboardWorkflow()
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._persistence = persistence or PersistenceManager()
        self._dashboard_renderer = DashboardRenderer()

    async def handle_upload(self, *, filename: str, payload: bytes, metadata: UploadMetadata) -> UploadSession:
        sanitized_filename = filename or "dataset.csv"
        session_metadata = UploadMetadataPayload(
            scenario_name=metadata.scenario_name,
            objective=metadata.objective,
            notes=metadata.notes,
        )
        record = await self._store.create_session(metadata=session_metadata, filename=sanitized_filename)
        logger.info(
            "Upload received",
            extra={
                "session_id": record.session_id,
                "filename": sanitized_filename,
                "scenario": metadata.scenario_name,
            },
        )
        dataset_path = await asyncio.to_thread(self._write_dataset, record.session_id, sanitized_filename, payload)
        blob_path, dataset_url = await self._persistence.persist_dataset(
            record.session_id,
            sanitized_filename,
            payload,
        )
        await self._store.attach_dataset_paths(
            record.session_id,
            local_path=dataset_path,
            blob_path=blob_path,
            dataset_url=dataset_url,
        )
        self._schedule_workflow(record.session_id)
        return UploadSession(
            session_id=record.session_id,
            uploaded_at=record.uploaded_at,
            next_poll_in_ms=record.next_poll_in_ms,
        )

    async def get_status(self, session_id: str) -> StatusResponse:
        record = await self._store.get(session_id)
        ordered_entries = sorted(
            record.status_entries,
            key=lambda entry: entry.started_at or record.uploaded_at,
        )
        payload = [self._convert_status(entry) for entry in ordered_entries]
        return StatusResponse(
            entries=payload,
            is_complete=record.is_complete,
            next_poll_in_ms=record.next_poll_in_ms,
        )

    async def get_dashboard(self, session_id: str) -> DashboardResponse:
        record = await self._store.get(session_id)
        if not record.dashboard:
            raise DashboardNotReadyError("Dashboard is still generating")
        dashboard = record.dashboard
        return DashboardResponse(
            iframe_url=dashboard.iframe_url,
            metrics=[
                MetricSummary(label=metric.label, value=metric.value, delta=metric.delta, trend=metric.trend)
                for metric in dashboard.metrics
            ],
            charts=[
                ChartConfig(
                    id=chart.id,
                    title=chart.title,
                    description=chart.description,
                    iframe_url=chart.iframe_url,
                    plotly_spec=chart.plotly_spec,
                )
                for chart in dashboard.charts
            ],
        )

    async def get_events(self, session_id: str) -> tuple[list[dict[str, Any]], str | None]:
        record = await self._store.get(session_id)
        return list(record.events), record.events_url

    def _schedule_workflow(self, session_id: str) -> None:
        logger.info("Scheduling workflow", extra={"session_id": session_id})
        task = asyncio.create_task(self._run_workflow(session_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _run_workflow(self, session_id: str) -> None:
        try:
            logger.info("Workflow started", extra={"session_id": session_id})
            record = await self._store.get(session_id)
            if not record.dataset_local_path:
                logger.error("Session %s missing dataset path", session_id)
                return
            await self._record_step_state(session_id, step_id="profile", tool_name="Profiler", state="running")
            await self._record_step_state(session_id, step_id="planner", tool_name="Planner", state="idle")
            execution: WorkflowExecution = await asyncio.to_thread(
                self._workflow.run_with_events,
                record.dataset_local_path,
                dataset_name=record.metadata.scenario_name,
                session_id=record.session_id,
            )
            await self._persist_workflow_events(session_id, execution.events)
            result = execution.result
            await self._record_step_state(session_id, step_id="profile", tool_name="Profiler", state="success")
            if result.plan:
                await self._record_step_state(session_id, step_id="planner", tool_name="Planner", state="running")
                await self._persist_outputs(record, result)
                await self._record_step_state(session_id, step_id="planner", tool_name="Planner", state="success")
            else:
                await self._persist_outputs(record, result)
            logger.info(
                "Workflow completed",
                extra={
                    "session_id": session_id,
                    "plan_produced": bool(result.plan),
                },
            )
        except Exception:  # pragma: no cover - guardrail for background task
            logger.exception("Workflow execution failed for session %s", session_id)
            await self._record_step_state(session_id, step_id="planner", tool_name="Planner", state="error")

    async def _record_step_state(
        self,
        session_id: str,
        *,
        step_id: str,
        tool_name: str,
        state: str,
        reasoning: str = "",
    ) -> None:
        record = await self._store.get(session_id)
        existing = next((entry for entry in record.status_entries if entry.id == step_id), None)
        now = datetime.now(timezone.utc)
        snapshot = AgentStepSnapshot(
            id=step_id,
            tool_name=tool_name,
            reasoning=reasoning or (existing.reasoning if existing else ""),
            state=state,
            started_at=existing.started_at if existing and existing.started_at else (now if state == "running" else None),
            finished_at=now if state in {"success", "error"} else (existing.finished_at if existing else None),
            duration_ms=existing.duration_ms if existing else None,
            retry_count=existing.retry_count if existing else 0,
            metadata=dict(existing.metadata) if existing else {},
        )
        await self._store.upsert_status(session_id, snapshot)
        logger.info(
            "Agent step update",
            extra={
                "session_id": session_id,
                "step_id": step_id,
                "state": state,
            },
        )

    def _convert_status(self, snapshot: AgentStepSnapshot) -> AgentStatusEntry:
        return AgentStatusEntry(
            id=snapshot.id,
            tool_name=snapshot.tool_name,
            reasoning=snapshot.reasoning,
            state=snapshot.state,
            started_at=snapshot.started_at,
            finished_at=snapshot.finished_at,
            duration_ms=snapshot.duration_ms,
            retry_count=snapshot.retry_count,
            metadata=dict(snapshot.metadata),
        )

    async def _persist_outputs(self, record: SessionRecord, result: WorkflowResult) -> None:
        session_id = record.session_id
        payload: Dict[str, Any] = {
            "profile": result.profile,
        }
        if result.plan:
            payload["plan"] = result.plan

        results_blob, results_url = await self._persistence.persist_results(session_id, payload)
        await self._store.record_results(
            session_id,
            results_blob_path=results_blob,
            results_url=results_url,
        )

        render_result: RenderedDashboard | None = None
        if record.dataset_local_path:
            try:
                render_result = await asyncio.to_thread(
                    self._dashboard_renderer.render,
                    record.dataset_local_path,
                    result.plan,
                )
            except Exception:
                logger.exception("Dashboard renderer failed for session %s", session_id)

        dashboard_html = ""
        if render_result:
            dashboard_html = render_result.html
            logger.info(
                "Renderer finished",
                extra={
                    "session_id": session_id,
                    "renderer_source": render_result.source,
                    "charts_rendered": len(render_result.sections),
                    "charts_skipped": len(render_result.skipped),
                },
            )
        elif result.plan:
            dashboard_html = self._render_basic_dashboard(result.plan)
            logger.info(
                "Renderer fallback to preview",
                extra={"session_id": session_id, "reason": "chart_renderer_unavailable"},
            )
        else:
            logger.info("No renderer output", extra={"session_id": session_id, "reason": "plan_missing"})

        dashboard_artifacts = self._build_dashboard_artifacts(result.plan, render_result)
        dashboard_blob: str | None = None
        dashboard_url: str | None = None
        if dashboard_html:
            dashboard_blob, dashboard_url = await self._persistence.persist_dashboard_html(session_id, dashboard_html)
        if dashboard_artifacts is None:
            dashboard_artifacts = DashboardArtifacts(iframe_url="", metrics=[], charts=[])
        if dashboard_url:
            dashboard_artifacts.iframe_url = dashboard_url

        await self._store.save_dashboard(
            session_id,
            dashboard_artifacts,
            dashboard_blob_path=dashboard_blob,
            dashboard_url=dashboard_url,
        )

    async def _persist_workflow_events(self, session_id: str, events: list[WorkflowEventRecord]) -> None:
        serialized = [event.to_dict() for event in events]
        events_blob: str | None = None
        events_url: str | None = None
        if serialized:
            events_blob, events_url = await self._persistence.persist_events(session_id, serialized)
        await self._store.record_events(
            session_id,
            events=serialized,
            events_blob_path=events_blob,
            events_url=events_url,
        )

    def _build_dashboard_artifacts(
        self,
        plan_payload: Dict[str, Any] | None,
        render_result: RenderedDashboard | None,
    ) -> DashboardArtifacts | None:
        if render_result:
            charts = [
                ChartConfigPayload(
                    id=section.chart_id,
                    title=section.title,
                    description=section.description,
                    iframe_url=None,
                    plotly_spec=section.metadata,
                )
                for section in render_result.sections
            ]
            metrics = [
                MetricSummaryPayload(label="Renderer", value=render_result.source),
                MetricSummaryPayload(label="Charts Rendered", value=str(len(charts))),
            ]
            if render_result.skipped:
                metrics.append(
                    MetricSummaryPayload(
                        label="Skipped Charts",
                        value=str(len(render_result.skipped)),
                    )
                )
            return DashboardArtifacts(iframe_url="", metrics=metrics, charts=charts)

        if not plan_payload:
            return None
        charts_payload = self._extract_charts(plan_payload)
        metrics = [
            MetricSummaryPayload(label="Sections", value=str(charts_payload["sections"])),
            MetricSummaryPayload(label="Charts", value=str(len(charts_payload["charts"]))),
        ]
        charts = charts_payload["charts"]
        return DashboardArtifacts(iframe_url="", metrics=metrics, charts=charts)

    def _extract_charts(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        plan = payload.get("plan") or {}
        sections: list[Dict[str, Any]] = list(plan.get("sections", []))
        charts: list[ChartConfigPayload] = []
        for section in sections:
            section_desc = section.get("description") or ""
            for chart in section.get("charts", []) or []:
                charts.append(
                    ChartConfigPayload(
                        id=str(chart.get("id") or f"{section.get('title', 'section')}-{len(charts)+1}"),
                        title=chart.get("title") or section.get("title") or "Chart",
                        description=chart.get("insight") or section_desc,
                        iframe_url=None,
                        plotly_spec=None,
                    )
                )
        return {"sections": len(sections), "charts": charts}

    def _render_basic_dashboard(self, plan: Dict[str, Any]) -> str:
        sections = plan.get("plan", {}).get("sections") if "plan" in plan else plan.get("sections", [])
        html_parts = [
            "<!DOCTYPE html>",
            "<html lang=\"en\">",
            "<head>",
            "<meta charset=\"utf-8\" />",
            "<title>Generated Dashboard</title>",
            "<style>body{font-family:Arial,Helvetica,sans-serif;margin:1.5rem;}h2{margin-top:2rem;}ul{padding-left:1.2rem;}li{margin-bottom:0.6rem;}section{border-bottom:1px solid #eee;padding-bottom:1rem;}</style>",
            "</head>",
            "<body>",
            "<h1>Dashboard Plan Preview</h1>",
        ]
        for section in sections or []:
            html_parts.append("<section>")
            html_parts.append(f"<h2>{section.get('title', 'Section')}</h2>")
            if section.get("description"):
                html_parts.append(f"<p>{section['description']}</p>")
            html_parts.append("<ul>")
            for chart in section.get("charts", []) or []:
                title = chart.get("title") or chart.get("id") or "Chart"
                insight = chart.get("insight") or ""
                html_parts.append("<li>")
                html_parts.append(f"<strong>{title}</strong>")
                if insight:
                    html_parts.append(f"<div>{insight}</div>")
                html_parts.append("</li>")
            html_parts.append("</ul>")
            html_parts.append("</section>")
        html_parts.append("</body></html>")
        return "".join(html_parts)

    def _write_dataset(self, session_id: str, filename: str, payload: bytes) -> Path:
        session_dir = self._upload_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        target = session_dir / filename
        target.write_bytes(payload)
        return target


__all__ = ["SessionCoordinator", "SessionNotFoundError", "DashboardNotReadyError"]
