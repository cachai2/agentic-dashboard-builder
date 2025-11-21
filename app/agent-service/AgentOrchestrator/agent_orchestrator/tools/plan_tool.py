"""Tool that calls Ollama's structured `/api/chat` endpoint to obtain plans."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional, Type

import importlib.util
import sys
import types

import jsonschema
from ..settings import get_settings

try:  # pragma: no cover - fallback for local editing without the SDK installed
    from agent_framework import ai_function
except ImportError:  # pragma: no cover
    def ai_function(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(func: Any) -> Any:
            return func

        return decorator


def _detect_repo_root() -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "azure.yaml").exists():
            return parent
    return None


def _ensure_local_package(module_name: str, directory: Path) -> None:
    if module_name in sys.modules or not directory.exists():
        return

    init_file = directory / "__init__.py"
    if init_file.exists():
        spec = importlib.util.spec_from_file_location(
            module_name,
            init_file,
            submodule_search_locations=[str(directory)],
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return

    module = types.ModuleType(module_name)
    module.__path__ = [str(directory)]  # type: ignore[attr-defined]
    sys.modules[module_name] = module


_PLANNER_BOOTSTRAPPED = False


def _bootstrap_repo_planner_packages() -> None:
    global _PLANNER_BOOTSTRAPPED
    if _PLANNER_BOOTSTRAPPED:
        return

    repo_root = _detect_repo_root()
    if not repo_root:
        return

    registrations = [
        ("ollama_proxy_service", repo_root / "app" / "ollama-proxy-service" / "ollama_proxy_service"),
        (
            "ollama_proxy_service.app",
            repo_root / "app" / "ollama-proxy-service" / "ollama_proxy_service" / "app",
        ),
        (
            "OllamaStructuredJson",
            repo_root / "app" / "agent-service" / "OllamaStructuredJson" / "OllamaStructuredJson",
        ),
        (
            "OllamaStructuredJson.app",
            repo_root
            / "app"
            / "agent-service"
            / "OllamaStructuredJson"
            / "OllamaStructuredJson"
            / "app",
        ),
    ]
    for module_name, directory in registrations:
        _ensure_local_package(module_name, directory)

    _PLANNER_BOOTSTRAPPED = True


def _load_planner_modules():
    """Resolve planner helpers across the new and legacy package layouts."""

    _bootstrap_repo_planner_packages()

    try:
        from ollama_proxy_service.app.augmentations import augment_plan as _augment
        from ollama_proxy_service.app.builder import compute_prompt_hash as _hash, render_prompt as _render
        from ollama_proxy_service.app.client import OllamaClient as _Client
        from ollama_proxy_service.app.config import Settings as _PlannerSettings
        from ollama_proxy_service.app.validator import PlanValidator as _Validator

        return _augment, _hash, _render, _PlannerSettings, _Validator, _Client
    except ModuleNotFoundError:
        try:
            from OllamaStructuredJson.app.augmentations import augment_plan as _augment
            from OllamaStructuredJson.app.builder import compute_prompt_hash as _hash, render_prompt as _render
            from OllamaStructuredJson.app.client import OllamaClient as _Client
            from OllamaStructuredJson.app.config import Settings as _PlannerSettings
            from OllamaStructuredJson.app.validator import PlanValidator as _Validator

            return _augment, _hash, _render, _PlannerSettings, _Validator, _Client
        except ModuleNotFoundError:  # pragma: no cover - fallback to the Playground namespace dynamically
            from importlib import import_module

            _builder_module = import_module("Playground.OllamaStructuredJson.app.builder")
            _hash = _builder_module.compute_prompt_hash
            _render = _builder_module.render_prompt

            _config_module = import_module("Playground.OllamaStructuredJson.app.config")
            _PlannerSettings = _config_module.Settings

            _augment_module = import_module("Playground.OllamaStructuredJson.app.augmentations")
            _augment = _augment_module.augment_plan

            _validator_module = import_module("Playground.OllamaStructuredJson.app.validator")
            _Validator = _validator_module.PlanValidator

            _client_module = import_module("Playground.OllamaStructuredJson.app.client")
            _Client = _client_module.OllamaClient

            return _augment, _hash, _render, _PlannerSettings, _Validator, _Client


augment_plan, compute_prompt_hash, render_prompt, PlannerSettings, PlanValidator, GatewayClient = _load_planner_modules()
logger = logging.getLogger(__name__)


class _ValidatorFacade:
    """Compatibility layer across the legacy and proxy planner validators."""

    def __init__(self, validator: Any) -> None:
        self._validator = validator
        self._schema = getattr(validator, "schema", None)
        self._chart_schema = self._extract_chart_schema()

    @property
    def schema(self) -> Dict[str, Any]:
        if self._schema is None:
            raise AttributeError("Planner validator does not expose a schema")
        return self._schema

    def parse(self, plan_text: str) -> Dict[str, Any]:
        parse = getattr(self._validator, "parse", None)
        if callable(parse):
            return parse(plan_text)

        parse_and_validate = getattr(self._validator, "parse_and_validate", None)
        if callable(parse_and_validate):
            return parse_and_validate(plan_text)

        raise AttributeError("Planner validator missing parse() or parse_and_validate()")

    def validate(self, plan: Dict[str, Any]) -> None:
        validate = getattr(self._validator, "validate", None)
        if callable(validate):
            validate(plan)
            return

        jsonschema.validate(instance=plan, schema=self.schema)

    def filter_invalid_charts(self, plan: Dict[str, Any]) -> None:
        filter_fn = getattr(self._validator, "filter_invalid_charts", None)
        if callable(filter_fn):
            filter_fn(plan)
            return

        self._fallback_filter(plan)

    def _extract_chart_schema(self) -> Dict[str, Any] | None:
        if not isinstance(self._schema, dict):
            return None
        return (
            self._schema.get("properties", {})
            .get("sections", {})
            .get("items", {})
            .get("properties", {})
            .get("charts", {})
            .get("items")
        )

    def _fallback_filter(self, plan: Dict[str, Any]) -> None:
        sections = plan.get("sections")
        if not isinstance(sections, list):
            return

        cleaned_sections: list[Dict[str, Any]] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            charts = section.get("charts")
            if not isinstance(charts, list):
                continue
            valid_charts = [chart for chart in charts if self._is_valid_chart(chart)]
            if valid_charts:
                section["charts"] = valid_charts
                cleaned_sections.append(section)

        if cleaned_sections:
            plan["sections"] = cleaned_sections

    def _is_valid_chart(self, chart: Any) -> bool:
        if not isinstance(chart, dict):
            return False
        if self._chart_schema is None:
            return True
        try:
            jsonschema.validate(instance=chart, schema=self._chart_schema)
        except jsonschema.ValidationError:
            return False
        return True

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
        self._ollama_host = str(settings.ollama_host).rstrip("/")
        self._validator = _ValidatorFacade(PlanValidator(planner_settings))
        self._model_name = planner_settings.ollama_model
        self._mock_plan_path = _resolve_mock_plan_path()
        self._request_dump_dir = settings.planner_request_dump_dir
        self._gateway_settings = planner_settings
        self._embedded_client_cls: Type[Any] | None = GatewayClient if isinstance(GatewayClient, type) else None
        self._embedded_client: Any | None = None

    def generate(self, profile_summary: Dict[str, Any], session_id: Optional[str]) -> Dict[str, Any]:
        prompt_bundle = render_prompt(profile_summary, prompt_version=self._prompt_version)
        base_prompt = prompt_bundle["user"]
        start = perf_counter()
        last_error: Exception | None = None
        raw_response = ""

        if self._planner_mode == "mock":
            raw_response = self._mock_plan_path.read_text(encoding="utf-8")
            plan = self._validator.parse(raw_response)
            plan = self._ensure_valid_plan(plan)
            plan = augment_plan(plan, profile_summary)
            plan = self._ensure_valid_plan(plan)
            return self._build_success(plan, raw_response, 1, start, prompt_bundle, session_id)

        for attempt in range(2):
            try:
                raw_response = self._invoke_planner(prompt_bundle, session_id)
                plan = self._validator.parse(raw_response)
                plan = self._ensure_valid_plan(plan)
                plan = augment_plan(plan, profile_summary)
                plan = self._ensure_valid_plan(plan)
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

    def _invoke_planner(self, prompt_bundle: Dict[str, str], session_id: Optional[str]) -> str:
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
        self._dump_gateway_payload(payload, session_id)
        client = self._ensure_embedded_client()
        messages = payload["messages"]
        prompt_hash = prompt_bundle.get("prompt_hash")
        request_start = perf_counter()
        logger.info(
            "Planner request -> %s/api/chat (model=%s, session=%s, prompt_hash=%s)",
            self._ollama_host,
            self._model_name,
            session_id or "<none>",
            prompt_hash or "<missing>",
        )
        parsed, raw, _ = client.chat_json(
            messages,
            schema=self._validator.schema,
            model=self._model_name,
            temperature=0.1,
            stream=False,
        )
        duration = (perf_counter() - request_start) * 1000
        logger.info(
            "Planner response <- %s/api/chat (duration_ms=%.1f)",
            self._ollama_host,
            duration,
        )
        if not raw:
            raw = json.dumps(parsed)
        return raw

    def _ensure_embedded_client(self) -> Any:
        if self._embedded_client is None:
            if self._embedded_client_cls is None:
                raise RuntimeError("Embedded planner client unavailable")
            self._embedded_client = self._embedded_client_cls(self._gateway_settings)
        return self._embedded_client

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

    def _ensure_valid_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._validator.validate(plan)
            return plan
        except jsonschema.ValidationError as error:
            salvaged = self._attempt_salvage_plan(plan, error)
            self._validator.validate(salvaged)
            return salvaged

    def _attempt_salvage_plan(self, plan: Dict[str, Any], error: jsonschema.ValidationError) -> Dict[str, Any]:
        path = list(error.path)
        removal_metadata = self._remove_invalid_path(plan, path)
        if not removal_metadata:
            raise error

        removal_metadata["error_path"] = path
        try:
            self._validator.filter_invalid_charts(plan)
        except ValueError as cleanup_error:
            raise error from cleanup_error

        logger.warning("Salvaged planner output by dropping invalid chart", extra=removal_metadata)
        return plan

    def _remove_invalid_path(self, plan: Dict[str, Any], path: list[Any]) -> Dict[str, Any] | None:
        chart_metadata = self._remove_chart_at_path(plan, path)
        if chart_metadata:
            return chart_metadata
        return self._remove_section_at_path(plan, path)

    def _remove_chart_at_path(self, plan: Dict[str, Any], path: list[Any]) -> Dict[str, Any] | None:
        for idx, key in enumerate(path):
            if key == "charts" and idx + 1 < len(path):
                chart_index = path[idx + 1]
                if not isinstance(chart_index, int):
                    continue
                section_node = self._resolve_path(plan, path[:idx])
                charts: Any | None = None
                if isinstance(section_node, dict):
                    charts = section_node.get("charts")
                elif isinstance(section_node, list):
                    charts = section_node
                if isinstance(charts, list) and 0 <= chart_index < len(charts):
                    removed = charts.pop(chart_index)
                    section_title = section_node.get("title") if isinstance(section_node, dict) else None
                    chart_id = removed.get("id") if isinstance(removed, dict) else None
                    return {"section": section_title, "chart_index": chart_index, "chart_id": chart_id}
        return None

    def _remove_section_at_path(self, plan: Dict[str, Any], path: list[Any]) -> Dict[str, Any] | None:
        for idx, key in enumerate(path):
            if key == "sections" and idx + 1 < len(path):
                section_index = path[idx + 1]
                if not isinstance(section_index, int):
                    continue
                sections = plan.get("sections")
                if isinstance(sections, list) and 0 <= section_index < len(sections):
                    removed = sections.pop(section_index)
                    section_title = removed.get("title") if isinstance(removed, dict) else None
                    return {"section": section_title, "section_index": section_index}
        return None

    def _resolve_path(self, node: Any, path: list[Any]) -> Any:
        current = node
        for key in path:
            if isinstance(key, int):
                if not isinstance(current, list) or not (0 <= key < len(current)):
                    return None
                current = current[key]
            else:
                if not isinstance(current, dict):
                    return None
                current = current.get(key)
            if current is None:
                return None
        return current

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


def reset_planner_cache() -> None:
    """Reset the cached StructuredPlanner so tests can pick up new settings."""

    global _PLANNER_INSTANCE
    _PLANNER_INSTANCE = None


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
        repo_root / "ollama_proxy_service" / "samples" / "mock_plan.json",
        repo_root / "ollama-proxy-service" / "samples" / "mock_plan.json",
        repo_root.parent / "OllamaStructuredJson" / "samples" / "mock_plan.json",
        repo_root.parent / "agent-service" / "OllamaStructuredJson" / "samples" / "mock_plan.json",
        repo_root.parent / "ollama_proxy_service" / "samples" / "mock_plan.json",
        repo_root.parent / "ollama-proxy-service" / "samples" / "mock_plan.json",
        repo_root.parent / "Playground" / "OllamaStructuredJson" / "samples" / "mock_plan.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
