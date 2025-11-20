"""Configuration helpers for the Agent Orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings


class OrchestratorSettings(BaseSettings):
    """Environment-driven settings for the orchestrator workflow."""

    session_namespace: str = Field(
        default="ignite-demo",
        description="Namespace prefix applied to generated session identifiers.",
    )
    csv_profiler_endpoint: Optional[HttpUrl] = Field(
        default=None,
        description="Optional HTTP endpoint for the CSV profiler agent. If omitted the local module is used.",
    )
    csv_profiler_max_rows: Optional[int] = Field(
        default=5000,
        description="Maximum rows to sample when profiling locally. None means full dataset.",
        ge=1,
    )
    ollama_host: HttpUrl = Field(
        default="https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io",
        description="Base URL for the deployed Ollama endpoint.",
    )
    ollama_model: str = Field(default="gpt-oss:20b", description="Model name passed to Ollama.")
    prompt_version: str = Field(default="v1", description="Prompt template identifier.")
    ollama_timeout_seconds: float = Field(default=90.0, ge=5.0, description="HTTP timeout for Ollama calls.")
    plan_schema_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "schemas" / "dashboard_plan.schema.json",
        description="Path to the DashboardPlan JSON schema for validation.",
    )

    class Config:
        env_prefix = "ORCH_"
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> OrchestratorSettings:
    """Cached accessor so downstream modules reuse the same settings instance."""

    # Simple manual cache to avoid pulling in functools for now.
    global _SETTINGS_CACHE  # type: ignore
    try:
        return _SETTINGS_CACHE  # type: ignore
    except NameError:
        _SETTINGS_CACHE = OrchestratorSettings()
        return _SETTINGS_CACHE
