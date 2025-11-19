"""Batch runner that executes AutoVizAdapter on every dataset in sample-data."""
from __future__ import annotations

import argparse
from pathlib import Path

from app.autoviz_batch import SUPPORTED_SUFFIXES, render_autoviz_dashboard_for_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AutoViz across all datasets in sample-data/.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("sample-data"),
        help="Directory that contains raw sample datasets.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("artifacts"),
        help="Where to store the generated HTML dashboards.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=5000,
        help="Maximum number of rows from each dataset to pass into AutoViz (avoids giant artifacts).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir: Path = args.data_dir
    artifacts_dir: Path = args.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    datasets = sorted(p for p in data_dir.iterdir() if p.is_file())
    if not datasets:
        raise FileNotFoundError(f"No datasets found inside '{data_dir}'.")

    for dataset_path in datasets:
        suffix = dataset_path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            print(f"Skipping unsupported file: {dataset_path.name}")
            continue

        print(f"Rendering AutoViz dashboard for {dataset_path.name}")
        try:
            result = render_autoviz_dashboard_for_file(
                dataset_path,
                artifacts_dir=artifacts_dir,
                max_rows=args.max_rows,
            )
        except Exception as exc:
            print(f"Skipping {dataset_path.name}: {exc}")
            continue

        print(
            "  generated"
            f" {result.artifact_path.name}"
            f" ({len(result.metadata.get('columns', []))} columns)"
        )


if __name__ == "__main__":
    main()
