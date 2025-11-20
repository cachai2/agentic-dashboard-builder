from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class UploadMetadata(BaseModel):
    scenario_name: str = Field(alias="scenarioName")
    objective: str
    notes: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class UploadSession(BaseModel):
    session_id: str = Field(alias="sessionId")
    uploaded_at: datetime = Field(alias="uploadedAt")
    next_poll_in_ms: int = Field(alias="nextPollInMs", default=2_000)

    model_config = ConfigDict(populate_by_name=True)


class AgentStatusEntry(BaseModel):
    id: str
    tool_name: str = Field(alias="toolName")
    state: Literal["idle", "running", "success", "error"]
    reasoning: str
    started_at: Optional[datetime] = Field(alias="startedAt", default=None)
    finished_at: Optional[datetime] = Field(alias="finishedAt", default=None)
    duration_ms: Optional[int] = Field(alias="durationMs", default=None)
    retry_count: Optional[int] = Field(alias="retryCount", default=None)
    metadata: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class StatusResponse(BaseModel):
    entries: List[AgentStatusEntry]
    is_complete: bool = Field(alias="isComplete")
    next_poll_in_ms: int = Field(alias="nextPollInMs")

    model_config = ConfigDict(populate_by_name=True)


class MetricSummary(BaseModel):
    label: str
    value: str
    delta: Optional[str] = None
    trend: Optional[Literal["up", "down", "flat"]] = None


class ChartConfig(BaseModel):
    id: str
    title: str
    description: str
    iframe_url: Optional[str] = Field(alias="iframeUrl", default=None)
    plotly_spec: Optional[Dict[str, Any]] = Field(alias="plotlySpec", default=None)

    model_config = ConfigDict(populate_by_name=True)


class DashboardResponse(BaseModel):
    iframe_url: str = Field(alias="iframeUrl")
    metrics: List[MetricSummary]
    charts: List[ChartConfig]

    model_config = ConfigDict(populate_by_name=True)
