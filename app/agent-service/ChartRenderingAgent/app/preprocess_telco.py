"""Utility for cleaning and enriching the Telco churn sample dataset.

The raw Kaggle export ships with string-typed numerics, inconsistent
categorical whitespace, and no engineered fields. This module standardises
the data so every renderer can reuse the same CSV without bespoke guards.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


TENURE_BINS = [0, 12, 24, 36, 48, 60, 72, float("inf")]
TENURE_LABELS = [
    "0-12 mo",
    "13-24 mo",
    "25-36 mo",
    "37-48 mo",
    "49-60 mo",
    "61-72 mo",
    "72+ mo",
]

YES_NO_MAP = {"Yes": True, "No": False}
ADDON_COLUMNS = [
    "MultipleLines",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
]


def _clean_object_columns(df: pd.DataFrame) -> None:
    """Trim whitespace-only noise from object columns in-place."""

    object_cols = df.select_dtypes(include="object").columns
    for col in object_cols:
        df[col] = df[col].apply(lambda value: value.strip() if isinstance(value, str) else value)


def _add_boolean_flags(df: pd.DataFrame, columns: Iterable[str]) -> None:
    for col in columns:
        flag_name = f"{col.lower()}_flag"
        df[flag_name] = df[col].map(YES_NO_MAP)


def preprocess_telco_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned/enriched copy ready for downstream charts."""

    frame = df.copy(deep=True)
    _clean_object_columns(frame)

    # Numeric coercions and imputations
    frame["TotalCharges"] = pd.to_numeric(frame["TotalCharges"], errors="coerce")
    total_missing_mask = frame["TotalCharges"].isna()
    frame["total_charges_was_imputed"] = total_missing_mask
    frame.loc[total_missing_mask, "TotalCharges"] = (
        frame.loc[total_missing_mask, "MonthlyCharges"] * frame.loc[total_missing_mask, "tenure"]
    ).round(2)

    # Feature engineering helpers
    frame["tenure_band"] = pd.cut(
        frame["tenure"], bins=TENURE_BINS, labels=TENURE_LABELS, include_lowest=True, right=True
    )

    _add_boolean_flags(frame, ["Partner", "Dependents", "PaperlessBilling", "Churn"])
    frame["has_phone_service"] = frame["PhoneService"].eq("Yes")
    frame["has_internet_service"] = frame["InternetService"].ne("No")

    frame["contract_length_months"] = frame["Contract"].map(
        {"Month-to-month": 1, "One year": 12, "Two year": 24}
    )

    addon_counts = sum(frame[col].eq("Yes") for col in ADDON_COLUMNS)
    frame["addon_count"] = addon_counts.astype(int)

    monthly_mean = frame["MonthlyCharges"].mean()
    monthly_std = frame["MonthlyCharges"].std(ddof=0)
    frame["monthly_charges_zscore"] = (frame["MonthlyCharges"] - monthly_mean) / monthly_std

    # Value-density indicator helps anomaly & scatter charts without recomputing per chart
    frame["revenue_per_month_of_tenure"] = frame.apply(
        lambda row: row["TotalCharges"] / row["tenure"] if row["tenure"] > 0 else row["MonthlyCharges"],
        axis=1,
    )

    return frame


def preprocess_file(input_path: Path, output_path: Path) -> Path:
    df = pd.read_csv(input_path)
    cleaned = preprocess_telco_dataframe(df)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False)
    return output_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean/enrich the Telco churn dataset.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("samples/telco_churn.csv"),
        help="Path to the raw Telco churn CSV (default: samples/telco_churn.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("samples/telco_churn_clean.csv"),
        help="Destination for the enriched CSV (default: samples/telco_churn_clean.csv)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_path = preprocess_file(args.input, args.output)
    print(f"Wrote cleaned dataset to {output_path}")


if __name__ == "__main__":
    main()