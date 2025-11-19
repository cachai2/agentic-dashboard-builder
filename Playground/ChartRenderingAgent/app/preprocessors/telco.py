"""Preprocessing logic for the Telco customer churn dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .base import DatasetPreprocessor, register_preprocessor

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
    object_cols = df.select_dtypes(include="object").columns
    for col in object_cols:
        df[col] = df[col].apply(lambda value: value.strip() if isinstance(value, str) else value)


def _add_boolean_flags(df: pd.DataFrame, columns: Iterable[str]) -> None:
    for col in columns:
        flag_name = f"{col.lower()}_flag"
        df[flag_name] = df[col].map(YES_NO_MAP)


@dataclass(slots=True)
class TelcoPreprocessor(DatasetPreprocessor):
    name: str = "telco_churn"
    description: str = "Clean Kaggle Telco churn data with enriched helper fields"
    default_input: Path = Path("samples/telco_churn.csv")
    default_output: Path = Path("samples/telco_churn_clean.csv")

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy(deep=True)
        _clean_object_columns(frame)

        frame["TotalCharges"] = pd.to_numeric(frame["TotalCharges"], errors="coerce")
        total_missing_mask = frame["TotalCharges"].isna()
        frame["total_charges_was_imputed"] = total_missing_mask
        frame.loc[total_missing_mask, "TotalCharges"] = (
            frame.loc[total_missing_mask, "MonthlyCharges"] * frame.loc[total_missing_mask, "tenure"]
        ).round(2)

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

        frame["revenue_per_month_of_tenure"] = frame.apply(
            lambda row: row["TotalCharges"] / row["tenure"] if row["tenure"] > 0 else row["MonthlyCharges"],
            axis=1,
        )

        return frame


register_preprocessor(TelcoPreprocessor())
