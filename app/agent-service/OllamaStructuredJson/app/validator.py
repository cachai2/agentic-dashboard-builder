"""Validation helpers for structured DashboardPlan responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema
import orjson

from .config import Settings, get_settings


class PlanValidator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._schema = self._load_schema(self.settings.schema_path)

    @staticmethod
    def _load_schema(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as schema_file:
            return json.load(schema_file)

    def parse_and_validate(self, plan_text: str) -> Dict[str, Any]:
        clean = self._strip_markdown_fences(plan_text)
        try:
            plan = orjson.loads(clean)
        except orjson.JSONDecodeError as exc:  # pragma: no cover - vendor-specific path
            raise ValueError("Planner returned invalid JSON") from exc

        jsonschema.validate(instance=plan, schema=self._schema)
        return plan

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @property
    def schema(self) -> Dict[str, Any]:
        return self._schema
