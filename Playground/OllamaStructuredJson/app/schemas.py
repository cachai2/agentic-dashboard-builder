from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    profile_summary: Dict[str, Any] = Field(..., description="Structured output from the profiling agent.")
    prompt_version: str = Field(default="v1", description="Identifier for the system prompt template used.")
    session_id: Optional[str] = Field(default=None, description="Correlation id shared across the orchestrator.")


class PlanMetadata(BaseModel):
    prompt_version: str
    model: str
    round_trips: int = Field(default=1, description="How many attempts were made before producing a valid plan.")
    duration_ms: float
    prompt_hash: str
    requested_at: datetime


class PlanResponse(BaseModel):
    plan: Dict[str, Any]
    metadata: PlanMetadata


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str
    model: str
