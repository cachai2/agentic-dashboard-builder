"""Configuration helpers for the Agent Orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_plan_schema_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "schemas" / "dashboard_plan.schema.json",
        repo_root / "CsvProfilerAgent" / "schemas" / "dashboard_plan.schema.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    # Fall back to the first candidate even if it does not exist yet so validation can surface the issue plainly.
    return candidates[0]


def _default_planner_dump_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "artifacts" / "planner_payloads"


class OrchestratorSettings(BaseSettings):
    """Environment-driven settings for the orchestrator workflow."""

    model_config = SettingsConfigDict(
        env_prefix="ORCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    planner_gateway_host: HttpUrl = Field(
        default="http://127.0.0.1:8801",
        description="Base URL for the OllamaStructuredJson gateway that exposes the /json endpoint.",
    )
    ollama_host: HttpUrl = Field(
        default="https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io",
        description="Base URL for the actual Ollama deployment that serves /api/chat.",
    )
    ollama_model: str = Field(default="gemma2:27b", description="Model name passed to Ollama.")
    prompt_version: str = Field(default="v1", description="Prompt template identifier.")
    ollama_timeout_seconds: float = Field(default=600.0, ge=5.0, description="HTTP timeout for Ollama calls.")
    plan_schema_path: Path = Field(
        default_factory=_default_plan_schema_path,
        description="Path to the DashboardPlan JSON schema for validation.",
    )
    planner_mode: Literal["remote", "mock"] = Field(
        default="remote",
        description="Switch between calling the remote Ollama service or using the mock plan sample.",
    )
    planner_request_dump_dir: Path = Field(
        default_factory=_default_planner_dump_dir,
        description="Directory where planner-to-gateway payloads are written for debugging.",
    )


def get_settings() -> OrchestratorSettings:
    """Cached accessor so downstream modules reuse the same settings instance."""

    # Simple manual cache to avoid pulling in functools for now.
    global _SETTINGS_CACHE  # type: ignore
    try:
        return _SETTINGS_CACHE  # type: ignore
    except NameError:
        _SETTINGS_CACHE = OrchestratorSettings()
        return _SETTINGS_CACHE


def reset_settings_cache() -> None:
    """Clear the cached settings instance so tests can reload env overrides."""

    global _SETTINGS_CACHE  # type: ignore
    if "_SETTINGS_CACHE" in globals():
        del _SETTINGS_CACHE  # type: ignore
