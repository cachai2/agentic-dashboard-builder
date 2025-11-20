"""Tool that calls the structured JSON planner directly via the Ollama client."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional

from ..settings import get_settings

try:  # pragma: no cover - fallback for local editing without the SDK installed
    from agent_framework import ai_function
except ImportError:  # pragma: no cover
    def ai_function(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(func: Any) -> Any:
            return func

        return decorator

from Playground.OllamaStructuredJson.app.builder import compute_prompt_hash, render_prompt
from Playground.OllamaStructuredJson.app.client import OllamaClient
from Playground.OllamaStructuredJson.app.config import Settings as PlannerSettings
from Playground.OllamaStructuredJson.app.validator import PlanValidator

logger = logging.getLogger(__name__)

_MAX_INVALID_SNIPPET_CHARS = 2000


def _compress_whitespace(value: str) -> str:
    import re

    return re.sub(r"\s+", " ", value).strip()


def _build_retry_user_prompt(base_prompt: str, invalid_output: str, failure_reason: str) -> str:
    snippet = (invalid_output or "").strip() or "<empty response>"
    if len(snippet) > _MAX_INVALID_SNIPPET_CHARS:
        snippet = f"{snippet[:_MAX_INVALID_SNIPPET_CHARS]}\n...truncated..."

    reason = _compress_whitespace(failure_reason) or "unknown error"
    if len(reason) > 300:
        reason = f"{reason[:300]}..."

    instructions = (
        "\n\nThe previous response failed because it did not produce valid DashboardPlan JSON ("
        f"{reason}). Carefully fix the invalid output shown between <BEGIN_INVALID_OUTPUT> and "
        "<END_INVALID_OUTPUT> so it matches the schema exactly. Respond with ONLY the corrected JSON "
        "object — no commentary or markdown.\n"
        "<BEGIN_INVALID_OUTPUT>\n"
        f"{snippet}\n"
        "<END_INVALID_OUTPUT>\n"
    )
    return base_prompt + instructions


class StructuredPlanner:
    """Lightweight wrapper around the Ollama Structured JSON components."""

    def __init__(self) -> None:
        settings = get_settings()
        planner_settings = PlannerSettings(
            ollama_mode="remote",
            ollama_host=str(settings.ollama_host),
            ollama_model=settings.ollama_model,
            ollama_timeout_seconds=settings.ollama_timeout_seconds,
            schema_path=settings.plan_schema_path,
        )
        self._prompt_version = settings.prompt_version
        self._client = OllamaClient(planner_settings)
        self._validator = PlanValidator(planner_settings)
        self._model_name = planner_settings.ollama_model

    def generate(self, profile_summary: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        prompt_bundle = render_prompt(profile_summary, prompt_version=self._prompt_version)
        base_prompt = prompt_bundle["user"]
        start = perf_counter()
        last_error: Exception | None = None
        raw_response = ""

        for attempt in range(2):
            try:
                raw_response = self._client.generate_plan_text(prompt_bundle, self._validator.schema)
                plan = self._validator.parse_and_validate(raw_response)
                duration = (perf_counter() - start) * 1000
                metadata = {
                    "prompt_version": self._prompt_version,
                    "model": self._model_name,
                    "round_trips": attempt + 1,
                    "duration_ms": duration,
                    "prompt_hash": prompt_bundle["prompt_hash"],
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                }
                logger.info(
                    "Generated dashboard plan",
                    extra={
                        "duration_ms": round(duration, 2),
                        "round_trips": attempt + 1,
                        "model": self._model_name,
                    },
                )
                return {"plan": plan, "metadata": metadata, "raw_response": raw_response}
            except Exception as exc:  # pragma: no cover - relies on live service
                last_error = exc
                logger.warning("Planner attempt failed", exc_info=exc)
                if attempt == 0:
                    prompt_bundle["user"] = _build_retry_user_prompt(base_prompt, raw_response, str(exc))
                    prompt_bundle["prompt_hash"] = compute_prompt_hash(
                        prompt_bundle["system"], prompt_bundle["user"], prompt_bundle["prompt_version"]
                    )
                    continue
                raise

        raise RuntimeError("Planner failed unexpectedly") from last_error


_PLANNER_INSTANCE: StructuredPlanner | None = None


def _get_planner() -> StructuredPlanner:
    global _PLANNER_INSTANCE
    if _PLANNER_INSTANCE is None:
        _PLANNER_INSTANCE = StructuredPlanner()
    return _PLANNER_INSTANCE


@ai_function(
    name="generate_dashboard_plan",
    description="Call the structured JSON planner with a dataset profile and return the validated DashboardPlan.",
)
def generate_dashboard_plan(
    profile_summary: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Invoke the remote planner and return the parsed DashboardPlan plus metadata."""

    planner = _get_planner()
    return planner.generate(profile_summary=profile_summary, session_id=session_id)
