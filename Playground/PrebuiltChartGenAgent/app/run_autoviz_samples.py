"""Batch runner that executes AutoVizAdapter on every dataset in sample-data."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

import pandas as pd

from adapters.autoviz_adapter import AutoVizAdapter

SUPPORTED_SUFFIXES = {
    ".csv": {
        "reader": pd.read_csv,
        "kwargs": {},
    },
    ".tsv": {
        "reader": pd.read_csv,
        "kwargs": {"sep": "\t"},
    },
    ".json": {
        "reader": pd.read_json,
        "kwargs": {},
    },
    ".jsonl": {
        "reader": pd.read_json,
        "kwargs": {"lines": True},
    },
    ".xml": {
        "reader": pd.read_xml,
        "kwargs": {},
    },
}


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

        try:
            df = _load_dataframe(dataset_path, suffix)
        except Exception as exc:
            print(f"Skipping {dataset_path.name}: {exc}")
            continue
        if df.empty:
            print(f"Skipping empty dataset: {dataset_path.name}")
            continue

        df = df.head(args.max_rows)
        section = _build_plan_section(dataset_path, df)
        artifact_path = artifacts_dir / f"{dataset_path.stem}_autoviz.html"

        print(f"Rendering AutoViz dashboard for {dataset_path.name} -> {artifact_path.name}")
        adapter = AutoVizAdapter(section, output_path=artifact_path)
        result = adapter.render()
        print(f"  generated {result.artifact_path} ({len(result.metadata.get('columns', []))} columns)")


def _load_dataframe(dataset_path: Path, suffix: str) -> pd.DataFrame:
    config = SUPPORTED_SUFFIXES[suffix]
    reader = config["reader"]
    kwargs = config.get("kwargs", {})
    return reader(dataset_path, **kwargs)


def _build_plan_section(dataset_path: Path, dataframe: pd.DataFrame) -> Mapping[str, object]:
    dataset_records = dataframe.to_dict(orient="records")
    title = dataset_path.stem.replace("_", " ").title()
    dep_var = _infer_dep_var(dataframe)
    encodings = {"y": dep_var} if dep_var else {}

    return {
        "id": dataset_path.stem,
        "title": title,
        "chartType": "autoviz",
        "encodings": encodings,
        "dataset": {"records": dataset_records},
    }


def _infer_dep_var(dataframe: pd.DataFrame) -> str:
    numeric_cols = [
        col
        for col in dataframe.columns
        if pd.api.types.is_numeric_dtype(dataframe[col])
    ]
    return numeric_cols[0] if numeric_cols else ""


if __name__ == "__main__":
    main()
