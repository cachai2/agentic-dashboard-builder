"""Shared helpers for running AutoViz across raw datasets."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd

from adapters.autoviz_adapter import AutoVizAdapter
from adapters.base import AdapterResult

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


def render_autoviz_dashboard_for_file(
    dataset_path: Path,
    *,
    artifacts_dir: Path,
    max_rows: int = 5000,
) -> AdapterResult:
    """Load a dataset file, build a synthetic plan, and render AutoViz output."""
    suffix = dataset_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported dataset format '{dataset_path.suffix}'."
        )

    dataframe = _load_dataframe(dataset_path, suffix)
    if dataframe.empty:
        raise ValueError(f"Dataset '{dataset_path.name}' contains no rows.")

    if max_rows <= 0:
        raise ValueError("max_rows must be positive.")

    dataframe = dataframe.head(max_rows)
    section = _build_plan_section(dataset_path, dataframe)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{dataset_path.stem}_autoviz.html"

    adapter = AutoVizAdapter(section, output_path=artifact_path)
    return adapter.render()


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


__all__ = ["SUPPORTED_SUFFIXES", "render_autoviz_dashboard_for_file"]
