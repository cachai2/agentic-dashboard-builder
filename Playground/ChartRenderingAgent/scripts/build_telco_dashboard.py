"""Generate derived datasets and a dashboard plan for the Telco churn sample."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"
RAW_DATA_PATH = SAMPLES_DIR / "telco_churn_clean.csv"


def _ensure_input() -> pd.DataFrame:
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            "Expected cleaned Telco dataset at 'samples/telco_churn_clean.csv'. "
            "Run the generic preprocessor before building dashboard assets."
        )
    df = pd.read_csv(RAW_DATA_PATH)
    required = {"customerID", "MonthlyCharges", "TotalCharges", "tenure", "tenure_band", "addon_count", "churn_flag"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing required columns: {sorted(missing)}")
    return df


def build_timeseries(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    grouped = (
        df.groupby("tenure", dropna=False)
        .agg(
            active_customers=("customerID", "count"),
            churners=("churn_flag", "sum"),
            avg_monthly_charges=("MonthlyCharges", "mean"),
        )
        .reset_index()
        .sort_values("tenure")
    )
    base_date = pd.Timestamp("2020-01-01")
    grouped["period"] = base_date + pd.to_timedelta(grouped["tenure"] * 30, unit="D")
    grouped["churn_rate"] = grouped["churners"] / grouped["active_customers"].replace(0, pd.NA)
    grouped["churn_rate"] = grouped["churn_rate"].fillna(0.0)
    threshold = grouped["churn_rate"].mean() + 2 * grouped["churn_rate"].std(ddof=0)
    grouped["is_spike"] = grouped["churn_rate"] >= threshold
    timeseries = grouped[["period", "active_customers", "churn_rate", "avg_monthly_charges", "is_spike"]]
    timeseries.to_csv(SAMPLES_DIR / "telco_timeseries.csv", index=False)
    return timeseries, float(threshold)


def build_composition(df: pd.DataFrame) -> pd.DataFrame:
    comp = (
        df.groupby("tenure_band")["InternetService"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["DSL", "Fiber optic", "No"], fill_value=0)
        .reset_index()
    )
    comp.columns = ["tenure_band", "dsl", "fiber_optic", "no_service"]
    comp.to_csv(SAMPLES_DIR / "telco_composition.csv", index=False)
    return comp


def build_funnel(df: pd.DataFrame) -> pd.DataFrame:
    records = {
        "stage": [
            "All Customers",
            "Phone Service",
            "Internet Service",
            "Bundle Add-ons",
            "Churned",
        ],
        "count": [
            len(df),
            int(df["has_phone_service"].sum()),
            int(df["has_internet_service"].sum()),
            int((df["addon_count"] >= 2).sum()),
            int(df["churn_flag"].sum()),
        ],
    }
    prev_counts = [int(records["count"][0] * 0.97)]
    for value in records["count"][1:]:
        prev_counts.append(max(prev_counts[-1] - max(prev_counts[-1] * 0.05, 1), value))
    funnel = pd.DataFrame({"stage": records["stage"], "count": records["count"], "prev_count": prev_counts})
    funnel.to_csv(SAMPLES_DIR / "telco_funnel.csv", index=False)
    return funnel


def build_scatter(df: pd.DataFrame) -> pd.DataFrame:
    sample_size = min(800, len(df))
    scatter = df.sample(n=sample_size, random_state=42)[
        ["customerID", "MonthlyCharges", "TotalCharges", "tenure", "addon_count", "Churn"]
    ].copy()
    scatter.rename(
        columns={
            "MonthlyCharges": "monthly_charges",
            "TotalCharges": "total_charges",
            "Churn": "churn_label",
        },
        inplace=True,
    )
    scatter.to_csv(SAMPLES_DIR / "telco_scatter.csv", index=False)
    return scatter


def build_plan(df: pd.DataFrame, timeseries: pd.DataFrame, churn_threshold: float) -> dict:
    total_customers = len(df)
    churn_rate = df["churn_flag"].mean()
    avg_mrr = df["MonthlyCharges"].mean()
    avg_tenure = df["tenure"].mean()

    ts_tail = timeseries.tail(4)
    active_trend = ts_tail["active_customers"].round(0).tolist()
    churn_trend = (ts_tail["churn_rate"] * 100).round(2).tolist()

    churn_delta = (churn_trend[-1] - churn_trend[-2]) if len(churn_trend) >= 2 else 0.0
    customers_delta = (active_trend[-1] - active_trend[-2]) if len(active_trend) >= 2 else 0.0

    plan = {
        "datasets": [
            {"id": "telco_timeseries", "path": "samples/telco_timeseries.csv", "format": "csv"},
            {"id": "telco_base", "path": "samples/telco_churn_clean.csv", "format": "csv"},
            {"id": "telco_composition", "path": "samples/telco_composition.csv", "format": "csv"},
            {"id": "telco_scatter", "path": "samples/telco_scatter.csv", "format": "csv"},
            {"id": "telco_funnel", "path": "samples/telco_funnel.csv", "format": "csv"},
        ],
        "sections": [
            {
                "operation": "kpi",
                "title": "Telco Snapshot",
                "layout": "grid",
                "cards": [
                    {
                        "title": "Active Customers",
                        "value": float(total_customers),
                        "delta": {
                            "value": float(customers_delta),
                            "direction": "up" if customers_delta >= 0 else "down",
                            "label": "vs prior tenure bucket",
                        },
                        "trend": active_trend,
                        "trend_label": "customers",
                    },
                    {
                        "title": "Avg Monthly Charges",
                        "value": round(float(avg_mrr), 2),
                        "unit": "$",
                        "delta": {
                            "value": round(float(df.loc[df["paperlessbilling_flag"], "MonthlyCharges"].mean() - avg_mrr), 2)
                            if "paperlessbilling_flag" in df.columns
                            else 0.0,
                            "direction": "up" if avg_mrr >= 0 else "flat",
                            "label": "paperless uplift",
                        },
                        "trend": (timeseries["avg_monthly_charges"].tail(4).round(2)).tolist(),
                        "trend_label": "$",
                    },
                    {
                        "title": "Churn Rate",
                        "value": round(float(churn_rate * 100), 2),
                        "unit": "%",
                        "delta": {
                            "value": round(float(churn_delta), 2),
                            "direction": "down" if churn_delta <= 0 else "up",
                            "label": "pts",
                        },
                        "trend": churn_trend,
                        "trend_label": "%",
                    },
                ],
            },
            {
                "operation": "timeseries",
                "title": "Active Customers vs Churn Rate",
                "dataset": "telco_timeseries",
                "x": {"column": "period", "grain": "month"},
                "series": [
                    {"id": "active_customers", "column": "active_customers", "label": "Active Customers"},
                    {
                        "id": "churn_rate",
                        "column": "churn_rate",
                        "label": "Churn Rate",
                        "axis": "secondary",
                    },
                ],
                "options": {"rolling_window": 3},
            },
            {
                "operation": "groupby",
                "title": "Avg Monthly Charges by Contract",
                "dataset": "telco_base",
                "dimension": "Contract",
                "metric": "MonthlyCharges",
                "aggregation": "avg",
                "options": {"orientation": "horizontal", "limit": 5, "show_reference": True},
            },
            {
                "operation": "composition",
                "title": "Internet Service Mix by Tenure Band",
                "dataset": "telco_composition",
                "x": {"column": "tenure_band", "grain": "category"},
                "stacks": ["dsl", "fiber_optic", "no_service"],
                "options": {"normalize": True, "kind": "stacked_bar"},
            },
            {
                "operation": "distribution",
                "title": "Monthly Charges Distribution",
                "dataset": "telco_base",
                "metric": "MonthlyCharges",
                "options": {"bins": 40, "overlay": "density", "show_boxplot": True},
            },
            {
                "operation": "outliers",
                "title": "Churn Rate Spikes",
                "dataset": "telco_timeseries",
                "x": {"column": "period", "grain": "month"},
                "y": "churn_rate",
                "threshold": {"value": round(float(churn_threshold), 4), "direction": "above"},
                "flag_column": "is_spike",
            },
            {
                "operation": "scatter",
                "title": "Total vs Monthly Charges",
                "dataset": "telco_scatter",
                "x": "monthly_charges",
                "y": "total_charges",
                "size": "tenure",
                "color": "churn_label",
                "text": "customerID",
                "tooltip_fields": ["addon_count", "tenure"],
                "quadrant": {
                    "x": 70,
                    "y": 2000,
                    "labels": [
                        "Low Spend / Low Lifetime",
                        "High Spend / Low Lifetime",
                        "Low Spend / High Lifetime",
                        "High Spend / High Lifetime",
                    ],
                },
                "options": {"trendline": True, "opacity": 0.8},
            },
            {
                "operation": "funnel",
                "title": "Retention Funnel",
                "dataset": "telco_funnel",
                "stage_column": "stage",
                "value_column": "count",
                "comparison_column": "prev_count",
                "stages": [
                    "All Customers",
                    "Phone Service",
                    "Internet Service",
                    "Bundle Add-ons",
                    "Churned",
                ],
                "options": {"show_conversion": True, "show_delta": True},
            },
        ],
        "metadata": {"source": "Telco churn sample"},
    }
    return plan


def main() -> None:
    df = _ensure_input()
    timeseries, threshold = build_timeseries(df)
    build_composition(df)
    build_funnel(df)
    build_scatter(df)
    plan = build_plan(df, timeseries, threshold)
    plan_path = SAMPLES_DIR / "telco_dashboard_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Wrote telco dashboard plan to {plan_path}")


if __name__ == "__main__":
    main()
