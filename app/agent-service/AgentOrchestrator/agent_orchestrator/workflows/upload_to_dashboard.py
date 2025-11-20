"""Agent Framework workflow that profiles a dataset and optionally plans a dashboard."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Never

from agent_framework import WorkflowBuilder, WorkflowContext, WorkflowOutputEvent, executor

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


def _build_workflow():
    builder = WorkflowBuilder()
    builder.set_start_executor(_profile_executor)
    builder.add_edge(_profile_executor, _planner_executor)
    return builder.build()


@executor(id="profile_executor")
async def _profile_executor(message: OrchestratorRequest, ctx: WorkflowContext[ProfileEnvelope]) -> None:
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
        async for event in self._workflow.run_stream(request):
            if isinstance(event, WorkflowOutputEvent):
                return event.data
        raise RuntimeError("Workflow completed without producing an output")
