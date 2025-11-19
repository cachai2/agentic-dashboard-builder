"""Helper utilities shared between adapters."""
from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd


def dataset_to_dataframe(dataset: Mapping[str, object]) -> pd.DataFrame:
    """Convert a DashboardPlan dataset dict into a pandas DataFrame."""
    if "records" in dataset:
        return pd.DataFrame(dataset["records"])

    columns: Sequence[str] | None = dataset.get("columns")  # type: ignore[assignment]
    rows = dataset.get("rows")
    if columns and rows:
        return pd.DataFrame(rows, columns=columns)

    raise ValueError(
        "Dataset payload must include either 'records' or both 'columns' and 'rows'."
    )
