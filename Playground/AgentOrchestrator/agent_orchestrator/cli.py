"""Simple CLI entrypoint for the Agent Orchestrator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import orjson

from .settings import get_settings
from .workflows import UploadToDashboardWorkflow


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))


def run_cli(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Upload → Profile → Plan orchestration loop")
    parser.add_argument("csv", help="Path to the CSV file to profile and plan.")
    parser.add_argument("--dataset-name", help="Friendly dataset name override.")
    parser.add_argument("--session-id", help="Optional session identifier to propagate to downstream services.")
    parser.add_argument(
        "--max-rows",
        type=int,
        help="Override the profiling sample size. Defaults to the orchestrator setting.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory where profile.json and plan.json should be written.",
    )
    args = parser.parse_args(argv)

    csv_path = Path(args.csv).expanduser().resolve()
    workflow = UploadToDashboardWorkflow()
    result = workflow.run(
        csv_path,
        dataset_name=args.dataset_name,
        session_id=args.session_id,
        max_rows=args.max_rows,
    )

    print("Dataset Profile Summary (truncated):")
    print(json.dumps({"dataset_name": result.profile.get("dataset_name"), "columns": len(result.profile.get("columns", []))}, indent=2))
    print("\nPlanner Metadata:")
    print(json.dumps(result.plan.get("metadata", {}), indent=2))

    if args.output_dir:
        _write_json(result.profile, args.output_dir / "profile.json")
        _write_json(result.plan, args.output_dir / "plan.json")
        print(f"\nArtifacts written to {args.output_dir}")


if __name__ == "__main__":  # pragma: no cover
    run_cli()
