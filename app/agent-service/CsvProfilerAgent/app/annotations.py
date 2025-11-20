"""Derived signal helpers that enrich dataset profiles for downstream planners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

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

ADDON_COLUMNS = [
    "MultipleLines",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
]

LIKELY_TARGET_COLUMNS = {"churn", "churn_flag", "is_churn", "attrition", "churned"}
POSITIVE_VALUES = {"yes", "y", "true", "1", "t", "churned"}


@dataclass
class TargetSignal:
    column: str
    positive_label: str
    mask: pd.Series

    @property
    def rate_pct(self) -> float:
        return round(float(self.mask.mean() * 100), 2) if len(self.mask) else 0.0


def build_llm_annotations(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """Return curated insight blocks that LLM planners can lean on."""

    if df.empty:
        return None

    annotations: Dict[str, Any] = {
        "dataset_shape": {"rows": int(len(df)), "columns": int(len(df.columns))}
    }

    target_signal = _detect_target_signal(df)
    if target_signal:
        annotations["target_signal"] = {
            "column": target_signal.column,
            "positive_label": target_signal.positive_label,
            "overall_rate_pct": target_signal.rate_pct,
        }

    kpis = _kpi_block(df, target_signal)
    if kpis:
        annotations["kpis"] = kpis

    segments = _segment_blocks(df, target_signal)
    if segments:
        annotations["segments"] = segments

    funnel = _retention_funnel(df, target_signal)
    if funnel:
        annotations["retention_funnel"] = funnel

    loyalty_hint = _loyalty_hint(df, target_signal)
    if loyalty_hint:
        annotations["loyalty_hint"] = loyalty_hint

    drivers = _driver_candidates(df, target_signal)
    if drivers:
        annotations["driver_candidates"] = drivers

    return annotations if len(annotations) > 1 else None


def _detect_target_signal(df: pd.DataFrame) -> Optional[TargetSignal]:
    for column in df.columns:
        if column.lower() not in LIKELY_TARGET_COLUMNS:
            continue
        normalized = _normalize_string_series(df[column])
        unique_values = normalized.dropna().unique()
        if len(unique_values) <= 1:
            continue
        positive_mask = normalized.isin(POSITIVE_VALUES)
        positive_label = _first_matching_label(df[column], POSITIVE_VALUES)
        return TargetSignal(column=column, positive_label=positive_label, mask=positive_mask)
    return None


def _first_matching_label(series: pd.Series, candidates: Iterable[str]) -> str:
    normalized_candidates = {value.lower() for value in candidates}
    for value in series.dropna().unique():
        text = str(value).strip()
        if text.lower() in normalized_candidates:
            return text
    # Fall back to the first unique (non-null) string representation
    for value in series.dropna().unique():
        return str(value)
    return "positive"


def _kpi_block(df: pd.DataFrame, target: Optional[TargetSignal]) -> List[Dict[str, Any]]:
    kpis: List[Dict[str, Any]] = [
        {"id": "active_customers", "label": "Active Customers", "value": int(len(df))}
    ]

    if target:
        kpis.append(
            {
                "id": "overall_churn_rate",
                "label": f"{target.column} rate",
                "value_pct": target.rate_pct,
            }
        )

    if "MonthlyCharges" in df.columns:
        mean_value = pd.to_numeric(df["MonthlyCharges"], errors="coerce").mean()
        if pd.notna(mean_value):
            kpis.append(
                {
                    "id": "avg_monthly_charges",
                    "label": "Avg Monthly Charges",
                    "value": round(float(mean_value), 2),
                    "unit": "$",
                }
            )

    if "tenure" in df.columns:
        mean_tenure = pd.to_numeric(df["tenure"], errors="coerce").mean()
        if pd.notna(mean_tenure):
            kpis.append(
                {
                    "id": "avg_tenure_months",
                    "label": "Avg Tenure (mo)",
                    "value": round(float(mean_tenure), 1),
                }
            )

    return kpis


def _segment_blocks(df: pd.DataFrame, target: Optional[TargetSignal]) -> Dict[str, List[Dict[str, Any]]]:
    if target is None:
        return {}

    segments: Dict[str, List[Dict[str, Any]]] = {}

    for column in ["Contract", "InternetService", "PaymentMethod", "SeniorCitizen", "PaperlessBilling"]:
        stats = _segment_churn_table(df, column, target)
        if stats:
            segments[column] = stats

    if "tenure" in df.columns:
        tenure_series = pd.cut(
            pd.to_numeric(df["tenure"], errors="coerce"),
            bins=TENURE_BINS,
            labels=TENURE_LABELS,
            include_lowest=True,
            right=True,
        )
        tenure_stats = _segment_churn_table(df, "tenure_band", target, series=tenure_series)
        if tenure_stats:
            segments["tenure_band"] = tenure_stats

    return segments


def _segment_churn_table(
    df: pd.DataFrame,
    column_name: str,
    target: TargetSignal,
    series: Optional[pd.Series] = None,
    limit: int = 6,
) -> Optional[List[Dict[str, Any]]]:
    base_series = series if series is not None else df.get(column_name)
    if base_series is None:
        return None

    normalized = _normalize_string_series(base_series)
    frame = pd.DataFrame({"segment": normalized})
    frame["segment"] = frame["segment"].fillna("Unknown")
    frame["__positive"] = target.mask

    grouped = frame.groupby("segment", dropna=False, sort=False)
    stats: List[Dict[str, Any]] = []
    for value, group in grouped:
        if group.empty:
            continue
        churn_rate = group["__positive"].mean()
        stats.append(
            {
                "value": str(value),
                "customers": int(group.shape[0]),
                "churn_rate_pct": round(float(churn_rate * 100), 2),
            }
        )

    stats.sort(key=lambda item: item["customers"], reverse=True)
    return stats[:limit] if stats else None


def _retention_funnel(df: pd.DataFrame, target: Optional[TargetSignal]) -> Optional[Dict[str, Any]]:
    if df.empty:
        return None

    stages: List[Dict[str, Any]] = [
        {"stage": "All Customers", "count": int(len(df)), "definition": "All rows"}
    ]

    if "PhoneService" in df.columns:
        phone_count = int(_mask_yes(df["PhoneService"]).sum())
        stages.append({"stage": "Phone Service", "count": phone_count, "definition": "PhoneService == 'Yes'"})

    if "InternetService" in df.columns:
        internet_count = int(df["InternetService"].astype("string").str.lower().ne("no").sum())
        stages.append(
            {
                "stage": "Internet Service",
                "count": internet_count,
                "definition": "InternetService != 'No'",
            }
        )

    addon_subset = [col for col in ADDON_COLUMNS if col in df.columns]
    if addon_subset:
        addon_flags = pd.DataFrame({col: _mask_yes(df[col]) for col in addon_subset})
        bundle_count = int((addon_flags.sum(axis=1) >= 2).sum())
        stages.append(
            {
                "stage": "Bundle Add-ons",
                "count": bundle_count,
                "definition": "At least two add-on services",
            }
        )

    if target is not None:
        churned_count = int(target.mask.sum())
        stages.append(
            {
                "stage": "Churned",
                "count": churned_count,
                "definition": f"{target.column} == '{target.positive_label}'",
            }
        )

    return {"stages": stages} if len(stages) > 1 else None


def _loyalty_hint(df: pd.DataFrame, target: Optional[TargetSignal]) -> Optional[Dict[str, Any]]:
    required_columns = {"MonthlyCharges", "TotalCharges", "tenure"}
    if not required_columns.issubset(df.columns):
        return None

    monthly = pd.to_numeric(df["MonthlyCharges"], errors="coerce")
    total = pd.to_numeric(df["TotalCharges"], errors="coerce")
    tenure = pd.to_numeric(df["tenure"], errors="coerce")
    valid_mask = monthly.notna() & total.notna() & tenure.notna()
    if valid_mask.sum() < 10:
        return None

    high_spend_short_tenure = (tenure < 12) & (monthly >= monthly.quantile(0.75))
    hint: Dict[str, Any] = {
        "columns": {
            "x": "MonthlyCharges",
            "y": "TotalCharges",
            "size": "tenure",
        },
        "high_spend_short_tenure_share_pct": round(
            float(high_spend_short_tenure.sum() / valid_mask.sum() * 100), 2
        ),
    }

    if target is not None:
        positive_series = target.mask
        high_rate = positive_series[high_spend_short_tenure & valid_mask].mean()
        other_rate = positive_series[~high_spend_short_tenure & valid_mask].mean()
        hint["columns"]["color"] = target.column
        hint["high_spend_short_tenure_churn_pct"] = _pct(high_rate)
        hint["other_segments_churn_pct"] = _pct(other_rate)

    return hint


def _driver_candidates(df: pd.DataFrame, target: Optional[TargetSignal]) -> List[Dict[str, Any]]:
    if target is None:
        return []

    driver_columns = [
        "Contract",
        "InternetService",
        "PaymentMethod",
        "TechSupport",
        "OnlineSecurity",
        "PaperlessBilling",
        "SeniorCitizen",
    ]

    drivers: List[Dict[str, Any]] = []
    for column in driver_columns:
        stats = _segment_churn_table(df, column, target)
        if not stats or len(stats) < 2:
            continue
        sorted_by_rate = sorted(stats, key=lambda item: item["churn_rate_pct"])
        delta = sorted_by_rate[-1]["churn_rate_pct"] - sorted_by_rate[0]["churn_rate_pct"]
        if delta < 1.0:
            continue
        drivers.append(
            {
                "feature": column,
                "max_value": sorted_by_rate[-1]["value"],
                "max_rate_pct": sorted_by_rate[-1]["churn_rate_pct"],
                "min_value": sorted_by_rate[0]["value"],
                "min_rate_pct": sorted_by_rate[0]["churn_rate_pct"],
                "delta_pct": round(float(delta), 2),
            }
        )

    drivers.sort(key=lambda item: item["delta_pct"], reverse=True)
    return drivers[:5]


def _mask_yes(series: pd.Series) -> pd.Series:
    return _normalize_string_series(series).isin(POSITIVE_VALUES)


def _normalize_string_series(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.lower()


def _pct(value: float) -> float:
    return round(float(value * 100), 2) if pd.notna(value) else 0.0


__all__ = ["build_llm_annotations"]
