"""Configuration helpers for the Ollama planner service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseSettings, Field


PACKAGE_ROOT = Path(__file__).resolve().parent
APP_ROOT = PACKAGE_ROOT.parent
REPO_ROOT = APP_ROOT.parent


class Settings(BaseSettings):
    ollama_mode: Literal["mock", "remote"] = Field(
        default="mock",
        validation_alias="OLLAMA_MODE",
        description="Controls whether the service calls a remote Ollama host or returns a canned response.",
    )
    ollama_host: str = Field(
        default="http://localhost:11434",
        validation_alias="OLLAMA_HOST",
        description="Base URL for the Ollama HTTP endpoint when running in remote mode.",
    )
    ollama_model: str = Field(
        default="gpt-oss:20b",
        validation_alias="OLLAMA_MODEL",
        description="Model identifier passed to the Ollama API.",
    )
    ollama_timeout_seconds: float = Field(
        default=90,
        validation_alias="OLLAMA_TIMEOUT_SECONDS",
        description="HTTP timeout for Ollama completions.",
    )
    ollama_send_json_schema: bool = Field(
        default=True,
        validation_alias="OLLAMA_SEND_JSON_SCHEMA",
        description="If true, include the DashboardPlan schema via the Ollama format parameter.",
    )
    ollama_force_json_mode: bool = Field(
        default=True,
        validation_alias="OLLAMA_FORCE_JSON_MODE",
        description="When no schema is attached, force Ollama JSON mode.",
    )
    schema_path: Path = Field(
        default=REPO_ROOT / "schemas" / "dashboard_plan.schema.json",
        validation_alias="PLAN_SCHEMA_PATH",
    )
    prompt_dir: Path = Field(
        default=APP_ROOT / "prompts",
        validation_alias="PROMPT_DIR",
    )
    service_port: int = Field(
        default=8801,
        validation_alias="PORT",
        description="Port uvicorn should bind to when launched locally.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
