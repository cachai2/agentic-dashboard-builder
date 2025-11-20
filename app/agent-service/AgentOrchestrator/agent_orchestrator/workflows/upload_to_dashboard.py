"""Sequential workflow that profiles a dataset and requests a dashboard plan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..tools import generate_dashboard_plan, profile_dataset


@dataclass
class WorkflowResult:
    """Output of the upload → plan workflow."""

    profile: Dict[str, Any]
    plan: Optional[Dict[str, Any]] = None


class UploadToDashboardWorkflow:
    """Minimal orchestrator that chains the profiling and planning tools."""

    def run(
        self,
        csv_path: Path,
        *,
        dataset_name: Optional[str] = None,
        session_id: Optional[str] = None,
        max_rows: Optional[int] = None,
        skip_planner: bool = False,
    ) -> WorkflowResult:
        profile = profile_dataset(
            csv_path=str(csv_path),
            dataset_name=dataset_name,
            max_rows=max_rows,
        )
        plan = None
        if not skip_planner:
            plan = generate_dashboard_plan(profile_summary=profile, session_id=session_id)
        return WorkflowResult(profile=profile, plan=plan)
