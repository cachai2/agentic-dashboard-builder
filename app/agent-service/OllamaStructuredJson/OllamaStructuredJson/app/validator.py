"""Validation helpers for structured DashboardPlan responses."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import jsonschema
import orjson

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class PlanValidator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._schema = self._load_schema(self.settings.schema_path)
        self._chart_schema = (
            self._schema.get("properties", {})
            .get("sections", {})
            .get("items", {})
            .get("properties", {})
            .get("charts", {})
            .get("items")
        )

    @staticmethod
    def _load_schema(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as schema_file:
            return json.load(schema_file)

    def parse(self, plan_text: str) -> Dict[str, Any]:
        clean = self._strip_markdown_fences(plan_text)
        try:
            plan = orjson.loads(clean)
        except orjson.JSONDecodeError as exc:  # pragma: no cover - vendor-specific path
            raise ValueError("Planner returned invalid JSON") from exc

        description = plan.get("description")
        if not isinstance(description, str) or not description.strip():
            plan["description"] = "Auto-generated dashboard plan"

        self.filter_invalid_charts(plan)
        return plan

    def validate(self, plan: Dict[str, Any]) -> None:
        jsonschema.validate(instance=plan, schema=self._schema)

    def parse_and_validate(self, plan_text: str) -> Dict[str, Any]:
        plan = self.parse(plan_text)
        self.validate(plan)
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

    def filter_invalid_charts(self, plan: Dict[str, Any]) -> None:
        sections = plan.get("sections")
        if not isinstance(sections, list):
            return

        cleaned_sections: list[Dict[str, Any]] = []
        removed_charts = 0
        for section in sections:
            if not isinstance(section, dict):
                continue

            charts = section.get("charts")
            if not isinstance(charts, list):
                logger.warning(
                    "Dropping section missing chart list",
                    extra={"section": section.get("title")},
                )
                continue

            valid_charts: list[Dict[str, Any]] = []
            for chart in charts:
                if self._is_valid_chart(chart):
                    valid_charts.append(chart)
                else:
                    removed_charts += 1
                    logger.warning(
                        "Dropping invalid chart from planner output",
                        extra={"chart_id": chart.get("id"), "section": section.get("title")},
                    )

            if valid_charts:
                section["charts"] = valid_charts
                cleaned_sections.append(section)
            else:
                logger.warning(
                    "Dropping section with no renderable charts",
                    extra={"section": section.get("title")},
                )

        if cleaned_sections:
            plan["sections"] = cleaned_sections
        elif removed_charts:
            raise ValueError("Planner returned charts but all failed validation")

    def _is_valid_chart(self, chart: Any) -> bool:
        if not isinstance(chart, dict):
            return False

        query = chart.get("query")
        if not isinstance(query, dict) or not query:
            return False

        if not chart.get("id") or not chart.get("type"):
            return False

        if not self._chart_schema:
            return True

        try:
            jsonschema.validate(instance=chart, schema=self._chart_schema)
        except jsonschema.ValidationError:
            return False
        return True
