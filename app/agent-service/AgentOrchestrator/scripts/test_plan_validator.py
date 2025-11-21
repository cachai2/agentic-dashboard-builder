"""Utility script to exercise the planner validator + salvage workflow locally."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import types

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
AGENT_SERVICE_ROOT = PROJECT_ROOT.parent
REPO_ROOT = SCRIPT_DIR.parents[3]
OLLAMA_PROXY_ROOT = REPO_ROOT / "app" / "ollama-proxy-service"
for path in (PROJECT_ROOT, AGENT_SERVICE_ROOT, REPO_ROOT, OLLAMA_PROXY_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _ensure_local_package(name: str, path: Path) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


_ensure_local_package("ollama_proxy_service", OLLAMA_PROXY_ROOT)
_ensure_local_package("ollama_proxy_service.app", OLLAMA_PROXY_ROOT / "app")

from agent_orchestrator.tools.plan_tool import StructuredPlanner
from OllamaStructuredJson.app.config import Settings as PlannerSettings
from OllamaStructuredJson.app.validator import PlanValidator

_DEFAULT_PLAN = (
    REPO_ROOT
    / "app"
    / "ollama-proxy-service"
    / "samples"
    / "mock_plan.json"
)

_MUTATION_CHOICES = {"none", "empty-query", "drop-operation"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test the planner validator fallback path.")
    parser.add_argument(
        "--plan",
        type=Path,
        default=_DEFAULT_PLAN,
        help="Path to a raw planner JSON response (defaults to mock_plan.json).",
    )
    parser.add_argument(
        "--mutation",
        choices=sorted(_MUTATION_CHOICES),
        default="empty-query",
        help="Optional chart mutation to trigger validation errors.",
    )
    parser.add_argument(
        "--section-index",
        type=int,
        default=0,
        help="Section index to mutate (when mutation != none).",
    )
    parser.add_argument(
        "--chart-index",
        type=int,
        default=0,
        help="Chart index to mutate (when mutation != none).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the salvaged plan JSON.",
    )
    return parser.parse_args()


def mutate_chart(plan: dict, *, section_index: int, chart_index: int, mutation: str) -> str:
    sections = plan.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Plan has no sections to mutate")
    try:
        section = sections[section_index]
        charts = section["charts"]
        chart = charts[chart_index]
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError("Invalid section/chart index for mutation") from exc

    if mutation == "empty-query":
        chart["query"] = {}
    elif mutation == "drop-operation":
        query = chart.get("query") or {}
        query.pop("operation", None)
        chart["query"] = query
    elif mutation == "none":
        pass
    else:  # pragma: no cover - guarded by argparse choices
        raise ValueError(f"Unsupported mutation: {mutation}")

    return str(chart.get("id"))


def main() -> None:
    args = parse_args()
    raw = args.plan.read_text(encoding="utf-8")
    planner = _build_planner_harness()
    plan = planner._validator.parse(raw)

    print(f"Loaded plan with {len(plan.get('sections', []))} section(s)")
    if args.mutation != "none":
        target_id = mutate_chart(
            plan,
            section_index=args.section_index,
            chart_index=args.chart_index,
            mutation=args.mutation,
        )
        print(f"Applied mutation '{args.mutation}' to chart id='{target_id}'")

    try:
        planner._validator.validate(plan)
        print("Plan already valid; salvage path not exercised")
        salvaged = plan
    except jsonschema.ValidationError as exc:
        print(f"Schema validation failed as expected: {exc.message}")
        salvaged = planner._ensure_valid_plan(plan)
        print(
            "Salvaged plan — now contains",
            len(salvaged.get("sections", [])),
            "section(s) and",
            sum(len(sec.get("charts", [])) for sec in salvaged.get("sections", [])),
            "chart(s)",
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(salvaged, indent=2), encoding="utf-8")
        print(f"Wrote sanitized plan to {args.output}")


def _build_planner_harness() -> StructuredPlanner:
    schema_candidates = [
        AGENT_SERVICE_ROOT / "schemas" / "dashboard_plan.schema.json",
        REPO_ROOT / "schemas" / "dashboard_plan.schema.json",
        REPO_ROOT.parent / "schemas" / "dashboard_plan.schema.json",
    ]
    schema_path = None
    for candidate in schema_candidates:
        if candidate.exists():
            schema_path = candidate
            break
    if schema_path is None:
        raise FileNotFoundError("Unable to locate dashboard_plan.schema.json in common locations")

    planner_settings = PlannerSettings(PLAN_SCHEMA_PATH=schema_path)
    dummy = StructuredPlanner.__new__(StructuredPlanner)
    dummy._validator = PlanValidator(planner_settings)  # type: ignore[attr-defined]
    return dummy


if __name__ == "__main__":
    main()
