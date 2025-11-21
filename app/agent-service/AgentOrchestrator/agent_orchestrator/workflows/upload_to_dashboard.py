"""Agent Framework workflow that profiles a dataset and optionally plans a dashboard."""

import asyncio
import logging
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Never

from agent_framework import (
    ExecutorEvent,
    ExecutorFailedEvent,
    RequestInfoEvent,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowEvent,
    WorkflowFailedEvent,
    WorkflowOutputEvent,
    WorkflowStatusEvent,
    executor,
)

from ..tools import generate_dashboard_plan, profile_dataset

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorRequest:
    """Input message that kicks off the workflow graph."""

    csv_path: Path
    dataset_name: Optional[str]
    session_id: Optional[str]
    max_rows: Optional[int]
    skip_planner: bool


@dataclass
class ProfileEnvelope:
    """Intermediate payload handed from the profiler executor to downstream nodes."""

    profile: Dict[str, Any]
    request: OrchestratorRequest


@dataclass
class WorkflowResult:
    """Output of the upload → plan workflow."""

    profile: Dict[str, Any]
    plan: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowEventRecord:
    """Serializable snapshot of an Agent Framework workflow event."""

    sequence: int
    type: str
    origin: str
    timestamp: datetime
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "type": self.type,
            "origin": self.origin,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }


@dataclass
class WorkflowExecution:
    """Result plus emitted events from a workflow run."""

    result: WorkflowResult
    events: List[WorkflowEventRecord]


def _build_workflow():
    builder = WorkflowBuilder()
    builder.set_start_executor(_profile_executor)
    builder.add_edge(_profile_executor, _planner_executor)
    return builder.build()


@executor(id="profile_executor")
async def _profile_executor(message: OrchestratorRequest, ctx: WorkflowContext[ProfileEnvelope]) -> None:
    logger.info(
        "Profiler agent started",
        extra={
            "session_id": message.session_id,
            "dataset_name": message.dataset_name or message.csv_path.stem,
            "max_rows": message.max_rows,
        },
    )
    profile = await asyncio.to_thread(
        profile_dataset,
        csv_path=str(message.csv_path),
        dataset_name=message.dataset_name,
        max_rows=message.max_rows,
    )
    logger.info(
        "Profile executor completed",
        extra={
            "dataset_name": message.dataset_name or message.csv_path.stem,
            "skip_planner": message.skip_planner,
        },
    )
    await ctx.send_message(ProfileEnvelope(profile=profile, request=message))


@executor(id="planner_executor")
async def _planner_executor(message: ProfileEnvelope, ctx: WorkflowContext[Never, WorkflowResult]) -> None:
    if message.request.skip_planner:
        await ctx.yield_output(WorkflowResult(profile=message.profile, plan=None))
        return

    logger.info(
        "Planner agent started",
        extra={
            "session_id": message.request.session_id,
            "profile_keys": list(message.profile.keys()),
        },
    )
    plan = await asyncio.to_thread(
        generate_dashboard_plan,
        profile_summary=message.profile,
        session_id=message.request.session_id,
    )
    logger.info(
        "Planner executor completed",
        extra={
            "session_id": message.request.session_id,
            "planner_metadata": plan.get("metadata"),
        },
    )
    await ctx.yield_output(WorkflowResult(profile=message.profile, plan=plan))


class UploadToDashboardWorkflow:
    """Agentic orchestrator that streams through profiler → planner executors."""

    def __init__(self) -> None:
        self._workflow = _build_workflow()

    def run(
        self,
        csv_path: Path,
        *,
        dataset_name: Optional[str] = None,
        session_id: Optional[str] = None,
        max_rows: Optional[int] = None,
        skip_planner: bool = False,
    ) -> WorkflowResult:
        request = OrchestratorRequest(
            csv_path=csv_path,
            dataset_name=dataset_name,
            session_id=session_id,
            max_rows=max_rows,
            skip_planner=skip_planner,
        )
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_async(request))
        raise RuntimeError("run() cannot execute inside an active event loop; use run_async() instead")

    async def run_async(self, request: OrchestratorRequest) -> WorkflowResult:
        execution = await self.run_with_events_async(request)
        return execution.result

    def run_with_events(
        self,
        csv_path: Path,
        *,
        dataset_name: Optional[str] = None,
        session_id: Optional[str] = None,
        max_rows: Optional[int] = None,
        skip_planner: bool = False,
    ) -> WorkflowExecution:
        request = OrchestratorRequest(
            csv_path=csv_path,
            dataset_name=dataset_name,
            session_id=session_id,
            max_rows=max_rows,
            skip_planner=skip_planner,
        )
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_with_events_async(request))
        raise RuntimeError("run_with_events() cannot execute inside an active event loop; use run_with_events_async() instead")

    async def run_with_events_async(self, request: OrchestratorRequest) -> WorkflowExecution:
        events: List[WorkflowEventRecord] = []
        sequence = 0
        async for event in self._workflow.run_stream(request):
            events.append(_serialize_event(sequence, event))
            sequence += 1
            if isinstance(event, WorkflowOutputEvent):
                return WorkflowExecution(result=event.data, events=events)
        raise RuntimeError("Workflow completed without producing an output")


def _serialize_event(sequence: int, event: WorkflowEvent) -> WorkflowEventRecord:
    payload: Dict[str, Any] = {}
    if isinstance(event, WorkflowStatusEvent):
        payload["state"] = event.state.value
        if event.data is not None:
            payload["data"] = _safe_payload(event.data)
    elif isinstance(event, WorkflowOutputEvent):
        payload["sourceExecutorId"] = event.source_executor_id
        payload["data"] = _safe_payload(event.data)
    elif isinstance(event, WorkflowFailedEvent):
        payload["error"] = asdict(event.details)
        if event.data is not None:
            payload["data"] = _safe_payload(event.data)
    elif isinstance(event, ExecutorFailedEvent):
        payload["executorId"] = event.executor_id
        payload["error"] = asdict(event.details)
    elif isinstance(event, ExecutorEvent):
        payload["executorId"] = event.executor_id
        if event.data is not None:
            payload["data"] = _safe_payload(event.data)
    elif isinstance(event, RequestInfoEvent):
        payload = {
            "requestId": event.request_id,
            "sourceExecutorId": event.source_executor_id,
            "requestType": event.request_type.__name__,
            "responseType": event.response_type.__name__,
            "data": _safe_payload(event.data),
        }
    else:
        if event.data is not None:
            payload["data"] = _safe_payload(event.data)
    return WorkflowEventRecord(
        sequence=sequence,
        type=event.__class__.__name__,
        origin=str(event.origin),
        timestamp=datetime.now(timezone.utc),
        payload=payload,
    )


def _safe_payload(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, dict)):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:  # pragma: no cover - defensive
            return repr(value)
    if is_dataclass(value):
        try:
            return asdict(value)
        except Exception:  # pragma: no cover
            return repr(value)
    return repr(value)
