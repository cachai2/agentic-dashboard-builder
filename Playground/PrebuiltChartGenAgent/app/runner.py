"""CLI entry-point for running chart adapters."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from adapters import get_registered_adapters, resolve_adapter
from adapters.base import AdapterResult, BaseAdapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render dashboard sections via adapters.")
    parser.add_argument("--plan", required=True, help="Path to DashboardPlan JSON payload.")
    parser.add_argument("--adapter", required=True, help="Adapter name to execute.")
    parser.add_argument("--out", required=True, help="Destination artifact path (html/png).")
    parser.add_argument(
        "--section",
        help="Optional section id from the plan. Defaults to the first section if omitted.",
    )
    parser.add_argument(
        "--list-adapters",
        action="store_true",
        help="List registered adapters and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list_adapters:
        print("Registered adapters:")
        for name in sorted(get_registered_adapters()):
            print(f" - {name}")
        return

    plan = _load_plan(Path(args.plan))
    section = _select_section(plan, args.section)
    adapter_cls = resolve_adapter(args.adapter)
    adapter = adapter_cls(section, output_path=Path(args.out))
    result = adapter.render()
    _log_result(result)


def _load_plan(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _select_section(plan: Mapping[str, Any], section_id: str | None) -> Mapping[str, Any]:
    sections = plan.get("sections")
    if not sections:
        raise ValueError("DashboardPlan payload must include at least one section.")
    if section_id is None:
        return sections[0]
    for section in sections:
        if section.get("id") == section_id:
            return section
    raise KeyError(f"Section '{section_id}' not found in plan.")


def _log_result(result: AdapterResult) -> None:
    print(f"Artifact generated at: {result.artifact_path}")
    print("Metadata:")
    for key, value in result.metadata.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
