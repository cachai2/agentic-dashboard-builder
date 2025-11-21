"""Utility script to exercise the planner validator + salvage workflow locally."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
AGENT_SERVICE_ROOT = PROJECT_ROOT.parent
REPO_ROOT = SCRIPT_DIR.parents[3]
OLLAMA_PROXY_ROOT = REPO_ROOT / "app" / "ollama-proxy-service"
for path in (PROJECT_ROOT, AGENT_SERVICE_ROOT, REPO_ROOT, OLLAMA_PROXY_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from agent_orchestrator.tools.plan_tool import StructuredPlanner

_DEFAULT_PLAN = (
    Path(__file__).resolve().parents[2]
    / "OllamaStructuredJson"
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
    planner = StructuredPlanner()
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


if __name__ == "__main__":
    main()
