"""Configuration helpers for the Ollama Structured JSON playground."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
REPO_ROOT = PROJECT_ROOT.parent


class Settings(BaseSettings):
    ollama_mode: Literal["mock", "remote"] = Field(
        default="remote",
        validation_alias="OLLAMA_MODE",
        description="Controls whether the service calls a remote Ollama host or returns canned responses.",
    )
    ollama_host: str = Field(
        default="http://localhost:11434",
        validation_alias="OLLAMA_HOST",
        description="Base URL (scheme + host) for the Ollama HTTP endpoint when running in remote mode.",
    )
    ollama_api_path: str = Field(
        default="/api/chat",
        validation_alias="OLLAMA_API_PATH",
        description="Endpoint path appended to the Ollama host; use empty string when specifying a fully-qualified URL.",
    )
    ollama_model: str = Field(
        default="gemma2:27b",
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
        default=PROJECT_ROOT / "prompts",
        validation_alias="PROMPT_DIR",
    )
    request_dump_dir: Optional[Path] = Field(
        default=REPO_ROOT / "app" / "agent-service" / "artifacts" / "gateway_requests",
        validation_alias="OLLAMA_REQUEST_DUMP_DIR",
        description="If set, the gateway dumps outbound Ollama requests into this directory for debugging.",
    )
    service_port: int = Field(
        default=8801,
        validation_alias="PORT",
        description="Port uvicorn should bind to when launched locally.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
