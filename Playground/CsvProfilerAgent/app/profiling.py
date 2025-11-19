"""Deterministic helpers that compute dataset profile statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import pandas as pd
from pandas.api import types as ptypes

from .schemas import CategoricalStats, ColumnProfile, DatasetProfile, NumericStats, TopValue


@dataclass(frozen=True)
class ProfilingOptions:
    """Tunables for controlling profiling behavior."""

    max_rows: Optional[int] = None
    sample_seed: int = 42


@dataclass
class CsvSource:
    """Represents where CSV bytes originated from."""

    dataset_name: str
    bytes_: bytes


def _load_dataframe(csv_bytes: bytes) -> pd.DataFrame:
    return pd.read_csv(BytesIO(csv_bytes))


def _semantic_type(series: pd.Series) -> str:
    if ptypes.is_bool_dtype(series):
        return "boolean"
    if ptypes.is_numeric_dtype(series):
        return "numeric"
    if ptypes.is_datetime64_any_dtype(series):
        return "datetime"

    return "categorical"


def _numeric_stats(series: pd.Series) -> NumericStats:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return NumericStats(min=None, max=None, mean=None, stddev=None, p05=None, p95=None)
    return NumericStats(
        min=float(clean.min()),
        max=float(clean.max()),
        mean=float(clean.mean()),
        stddev=float(clean.std()),
        p05=float(clean.quantile(0.05)),
        p95=float(clean.quantile(0.95)),
    )


def _categorical_stats(series: pd.Series) -> CategoricalStats:
    total = max(len(series), 1)
    counts = series.astype("string").fillna("<NA>").value_counts().head(5)
    top_values = [
        TopValue(
            value=(None if value == "<NA>" else str(value)),
            count=int(count),
            percent=round(float(count / total * 100), 2),
        )
        for value, count in counts.items()
    ]
    return CategoricalStats(top_values=top_values)


def _profile_column(series: pd.Series, name: str) -> ColumnProfile:
    total = len(series)
    null_count = int(series.isna().sum())
    null_pct = round((null_count / total * 100) if total else 0.0, 4)
    distinct_count = int(series.nunique(dropna=True))
    example = None
    for value in series.dropna().head(3):
        example = str(value)
        break

    semantic = _semantic_type(series)
    numeric_stats = _numeric_stats(series) if semantic == "numeric" else None
    categorical_stats = _categorical_stats(series) if semantic == "categorical" else None

    return ColumnProfile(
        name=name,
        semantic_type=semantic,
        null_count=null_count,
        null_pct=null_pct,
        distinct_count=distinct_count,
        example=example,
        numeric_stats=numeric_stats,
        categorical_stats=categorical_stats,
    )


def _profile_dataframe(
    df: pd.DataFrame,
    dataset_name: str,
    options: Optional[ProfilingOptions] = None,
) -> DatasetProfile:
    options = options or ProfilingOptions()
    total_rows = int(len(df))
    sampled_df = df
    sampled_rows = total_rows
    if options.max_rows is not None and total_rows > options.max_rows:
        sampled_rows = int(options.max_rows)
        sampled_df = df.sample(n=options.max_rows, random_state=options.sample_seed)

    columns = [_profile_column(sampled_df[col], col) for col in sampled_df.columns]
    sampling_ratio = (
        1.0
        if total_rows == 0
        else round(sampled_rows / total_rows, 6)
    )
    return DatasetProfile(
        dataset_name=dataset_name,
        row_count=total_rows,
        sampled_row_count=sampled_rows,
        sampling_ratio=sampling_ratio,
        column_count=int(len(sampled_df.columns)),
        generated_at=datetime.now(timezone.utc),
        columns=columns,
    )


def profile_csv_path(
    path: str | Path,
    dataset_name: Optional[str] = None,
    options: Optional[ProfilingOptions] = None,
) -> DatasetProfile:
    path_obj = Path(path).expanduser().resolve()
    if not path_obj.exists():
        raise FileNotFoundError(f"CSV not found: {path_obj}")
    bytes_ = path_obj.read_bytes()
    df = _load_dataframe(bytes_)
    return _profile_dataframe(df, dataset_name or path_obj.stem, options)


def profile_csv_bytes(
    payload: bytes,
    dataset_name: str = "uploaded",
    options: Optional[ProfilingOptions] = None,
) -> DatasetProfile:
    df = _load_dataframe(payload)
    return _profile_dataframe(df, dataset_name, options)


__all__ = [
    "CsvSource",
    "ProfilingOptions",
    "profile_csv_path",
    "profile_csv_bytes",
]
