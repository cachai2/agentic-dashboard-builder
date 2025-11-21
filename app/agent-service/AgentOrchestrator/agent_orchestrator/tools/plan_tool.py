"""Tool that calls the shared Ollama gateway's JSON endpoint to obtain plans."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional

import jsonschema
from ..settings import get_settings

try:  # pragma: no cover - fallback for local editing without the SDK installed
    from agent_framework import ai_function
except ImportError:  # pragma: no cover
    def ai_function(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(func: Any) -> Any:
            return func

        return decorator

import httpx

try:
    from OllamaStructuredJson.app.augmentations import augment_plan
    from OllamaStructuredJson.app.builder import compute_prompt_hash, render_prompt
    from OllamaStructuredJson.app.config import Settings as PlannerSettings
    from OllamaStructuredJson.app.validator import PlanValidator
except ModuleNotFoundError:  # pragma: no cover - fallback to the Playground namespace dynamically
    from importlib import import_module

    _builder_module = import_module("Playground.OllamaStructuredJson.app.builder")
    compute_prompt_hash = _builder_module.compute_prompt_hash
    render_prompt = _builder_module.render_prompt

    _config_module = import_module("Playground.OllamaStructuredJson.app.config")
    PlannerSettings = _config_module.Settings

    _augment_module = import_module("Playground.OllamaStructuredJson.app.augmentations")
    augment_plan = _augment_module.augment_plan

    _validator_module = import_module("Playground.OllamaStructuredJson.app.validator")
    PlanValidator = _validator_module.PlanValidator

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
            OLLAMA_MODE="remote",
            OLLAMA_HOST=str(settings.ollama_host),
            OLLAMA_MODEL=settings.ollama_model,
            OLLAMA_TIMEOUT_SECONDS=settings.ollama_timeout_seconds,
            PLAN_SCHEMA_PATH=settings.plan_schema_path,
        )
        self._prompt_version = settings.prompt_version
        self._planner_mode = settings.planner_mode
        self._gateway_url = str(settings.planner_gateway_host).rstrip("/")
        self._http_client = httpx.Client(timeout=settings.ollama_timeout_seconds)
        self._validator = PlanValidator(planner_settings)
        self._model_name = planner_settings.ollama_model
        self._mock_plan_path = _resolve_mock_plan_path()
        self._request_dump_dir = settings.planner_request_dump_dir

    def generate(self, profile_summary: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        prompt_bundle = render_prompt(profile_summary, prompt_version=self._prompt_version)
        base_prompt = prompt_bundle["user"]
        start = perf_counter()
        last_error: Exception | None = None
        raw_response = ""

        if self._planner_mode == "mock":
            raw_response = self._mock_plan_path.read_text(encoding="utf-8")
            plan = self._validator.parse_and_validate(raw_response)
            plan = augment_plan(plan, profile_summary)
            jsonschema.validate(instance=plan, schema=self._validator.schema)
            return self._build_success(plan, raw_response, 1, start, prompt_bundle, session_id)

        for attempt in range(2):
            try:
                raw_response = self._invoke_gateway(prompt_bundle, session_id)
                plan = self._validator.parse_and_validate(raw_response)
                plan = augment_plan(plan, profile_summary)
                jsonschema.validate(instance=plan, schema=self._validator.schema)
                return self._build_success(plan, raw_response, attempt + 1, start, prompt_bundle, session_id)
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

    def _invoke_gateway(self, prompt_bundle: Dict[str, str], session_id: Optional[str]) -> str:
        payload = {
            "messages": [
                {"role": "system", "content": prompt_bundle["system"]},
                {"role": "user", "content": prompt_bundle["user"]},
            ],
            "schema": self._validator.schema,
            "model": self._model_name,
            "temperature": 0.1,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        if session_id:
            headers["X-Session-ID"] = session_id
        self._dump_gateway_payload(payload, session_id)
        response = self._http_client.post(f"{self._gateway_url}/json", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        raw = data.get("raw")
        if not raw and "content" in data:
            raw = json.dumps(data["content"])
        if not raw:
            raise RuntimeError("Gateway response missing content")
        return raw

    def _build_success(
        self,
        plan: Dict[str, Any],
        raw_response: str,
        attempts: int,
        start: float,
        prompt_bundle: Dict[str, Any],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        duration = (perf_counter() - start) * 1000
        metadata = {
            "prompt_version": self._prompt_version,
            "model": self._model_name,
            "round_trips": attempts,
            "duration_ms": duration,
            "prompt_hash": prompt_bundle["prompt_hash"],
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        }
        logger.info(
            "Generated dashboard plan",
            extra={
                "duration_ms": round(duration, 2),
                "round_trips": attempts,
                "model": self._model_name,
            },
        )
        return {"plan": plan, "metadata": metadata, "raw_response": raw_response}

    def _dump_gateway_payload(self, payload: Dict[str, Any], session_id: Optional[str]) -> None:
        dump_dir = self._request_dump_dir
        if not dump_dir:
            return
        try:
            dump_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            suffix = f"_{session_id}" if session_id else ""
            path = dump_dir / f"planner_payload{suffix}_{ts}.json"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - diagnostics only
            logger.warning("Failed to dump planner payload: %s", exc)


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


def _resolve_mock_plan_path() -> Path:
    """Find the mock plan sample regardless of repo layout."""

    repo_root = Path(__file__).resolve().parents[3]
    candidates = [
        repo_root / "OllamaStructuredJson" / "samples" / "mock_plan.json",
        repo_root / "agent-service" / "OllamaStructuredJson" / "samples" / "mock_plan.json",
        repo_root.parent / "OllamaStructuredJson" / "samples" / "mock_plan.json",
        repo_root.parent / "agent-service" / "OllamaStructuredJson" / "samples" / "mock_plan.json",
        repo_root.parent / "Playground" / "OllamaStructuredJson" / "samples" / "mock_plan.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
