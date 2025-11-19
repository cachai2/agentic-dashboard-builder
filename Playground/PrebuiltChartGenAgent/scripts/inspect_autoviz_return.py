"""Utility script to inspect AutoViz return payloads."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.autoviz_adapter import AutoVizAdapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect the object AutoViz returns for a dataset.")
    parser.add_argument("dataset", type=Path, help="Path to the raw dataset to inspect.")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=5000,
        help="Limit rows passed to AutoViz so the script stays quick.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path: Path = args.dataset
    df = pd.read_csv(dataset_path)

    section = {"dataset": {"records": df.to_dict(orient="records")}}
    adapter = AutoVizAdapter(section, output_path=(dataset_path.with_suffix(".html")))
    av = adapter._autoviz_class()
    result = av.AutoViz(
        filename="",
        sep=",",
        depVar="",
        dfte=df,
        header=0,
        verbose=0,
        lowess=False,
        chart_format="html",
        max_rows_analyzed=min(len(df), args.max_rows),
        max_cols_analyzed=len(df.columns),
        save_plot_dir=None,
    )

    print("type:", type(result))
    if hasattr(result, "__len__"):
        print("len:", len(result))
    if isinstance(result, dict):
        print("keys:", list(result.keys()))
    try:
        print("json:", json.dumps(result, default=_repr_obj, indent=2)[:2000])
    except TypeError:
        print("repr:", _repr_obj(result))


def _repr_obj(obj: Any) -> str:
    return repr(obj)


if __name__ == "__main__":
    main()
