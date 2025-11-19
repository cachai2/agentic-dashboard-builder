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
        try:
            plan = orjson.loads(plan_text)
        except orjson.JSONDecodeError as exc:  # pragma: no cover - orjson specific path
            raise ValueError("Planner returned invalid JSON") from exc

        jsonschema.validate(instance=plan, schema=self._schema)
        return plan
