from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ToolState = Literal["idle", "running", "success", "error"]


@dataclass(slots=True)
class UploadMetadataPayload:
    scenario_name: str
    objective: str
    notes: str | None = None


@dataclass(slots=True)
class AgentStepSnapshot:
    id: str
    tool_name: str
    reasoning: str
    state: ToolState = "idle"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    retry_count: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class MetricSummaryPayload:
    label: str
    value: str
    delta: str | None = None
    trend: Literal["up", "down", "flat"] | None = None


@dataclass(slots=True)
class ChartConfigPayload:
    id: str
    title: str
    description: str
    iframe_url: str | None = None
    plotly_spec: dict[str, Any] | None = None


@dataclass(slots=True)
class DashboardArtifacts:
    iframe_url: str
    metrics: list[MetricSummaryPayload] = field(default_factory=list)
    charts: list[ChartConfigPayload] = field(default_factory=list)


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    uploaded_at: datetime
    original_filename: str
    metadata: UploadMetadataPayload
    dataset_local_path: Path | None = None
    dataset_blob_path: str | None = None
    dataset_url: str | None = None
    status_entries: list[AgentStepSnapshot] = field(default_factory=list)
    is_complete: bool = False
    dashboard: DashboardArtifacts | None = None
    next_poll_in_ms: int = 2_000
    results_blob_path: str | None = None
    results_url: str | None = None
    dashboard_blob_path: str | None = None
    dashboard_url: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    events_blob_path: str | None = None
    events_url: str | None = None
