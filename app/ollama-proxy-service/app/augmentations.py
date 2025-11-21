"""Post-processing helpers that enrich planner output with deterministic charts."""

from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional


class PlanAugmentor:
    """Injects deterministic sections derived from profiler annotations."""

    def __init__(self, profile_summary: Dict[str, Any]) -> None:
        self._profile = profile_summary or {}
        self._annotations = self._profile.get("llm_annotations") or {}
        self._dataset_name = self._profile.get("dataset_name") or "uploaded_dataset"
        self._column_names = {col.get("name") for col in self._profile.get("columns", []) if col.get("name")}
        self._id_counter = itertools.count(1)

    def apply(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        if not self._annotations:
            return plan

        sections = plan.setdefault("sections", []) or []
        synthesized: List[Dict[str, Any]] = []

        if self._annotations.get("kpis") and not self._has_operation(plan, "kpi"):
            kpi_section = self._build_kpi_section()
            if kpi_section:
                synthesized.append(kpi_section)

        if self._annotations.get("retention_funnel") and not self._has_operation(plan, "funnel"):
            funnel_section = self._build_funnel_section()
            if funnel_section:
                synthesized.append(funnel_section)

        if self._annotations.get("loyalty_hint") and not self._has_operation(plan, "scatter"):
            loyalty_section = self._build_loyalty_scatter_section()
            if loyalty_section:
                synthesized.append(loyalty_section)

        if synthesized:
            plan["sections"] = synthesized + sections
        return plan

    def _build_kpi_section(self) -> Optional[Dict[str, Any]]:
        cards: List[Dict[str, Any]] = []
        for entry in self._annotations.get("kpis", []):
            title = entry.get("label") or entry.get("id")
            if not title:
                continue
            value = entry.get("value")
            unit = entry.get("unit")
            if value is None and entry.get("value_pct") is not None:
                value = float(entry["value_pct"])
                unit = unit or "%"
            if value is None:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            cards.append(
                {
                    "title": str(title),
                    "value": numeric_value,
                    "unit": unit,
                    "trend": entry.get("trend") or [],
                    "trend_label": entry.get("trend_label"),
                }
            )
        if not cards:
            return None

        chart_id = self._make_chart_id("kpi")
        section_title = "Customer Snapshot"
        return {
            "id": self._make_section_id("kpi"),
            "title": section_title,
            "charts": [
                {
                    "id": chart_id,
                    "type": "kpi",
                    "title": section_title,
                    "insight": "Key customer health metrics derived from deterministic profiling signals.",
                    "query": {
                        "operation": "kpi",
                        "layout": "grid",
                        "cards": cards,
                    },
                }
            ],
        }

    def _build_funnel_section(self) -> Optional[Dict[str, Any]]:
        funnel = self._annotations.get("retention_funnel") or {}
        stages = funnel.get("stages") or []
        if len(stages) < 2:
            return None

        data_rows: List[Dict[str, Any]] = []
        previous_count: Optional[int] = None
        ordered_stage_labels: List[str] = []
        for stage in stages:
            label = stage.get("stage")
            count = stage.get("count")
            if label is None or count is None:
                continue
            ordered_stage_labels.append(str(label))
            row = {"stage": label, "count": count}
            if previous_count is not None:
                row["prev_count"] = previous_count
            previous_count = count
            definition = stage.get("definition")
            if definition:
                row["definition"] = definition
            data_rows.append(row)
        if len(data_rows) < 2:
            return None

        return {
            "id": self._make_section_id("funnel"),
            "title": "Retention Funnel",
            "charts": [
                {
                    "id": self._make_chart_id("funnel"),
                    "type": "funnel",
                    "title": "Retention Funnel",
                    "insight": "Shows drop-off from all customers through add-on bundles and churned accounts.",
                    "query": {
                        "operation": "funnel",
                        "dataset_hint": f"{self._dataset_name}_funnel",
                        "stage_column": "stage",
                        "value_column": "count",
                        "comparison_column": "prev_count",
                        "stages": ordered_stage_labels,
                        "options": {"show_conversion": True, "show_delta": True},
                        "data": data_rows,
                    },
                }
            ],
        }

    def _build_loyalty_scatter_section(self) -> Optional[Dict[str, Any]]:
        hint = self._annotations.get("loyalty_hint") or {}
        columns = hint.get("columns") or {}
        x_col = columns.get("x")
        y_col = columns.get("y")
        if not self._column_exists(x_col) or not self._column_exists(y_col):
            return None

        chart_id = self._make_chart_id("loyalty_scatter")
        section_title = "Loyalty vs Spend"
        insight_parts: List[str] = []
        high_pct = self._coerce_float(hint.get("high_spend_short_tenure_churn_pct"))
        other_pct = self._coerce_float(hint.get("other_segments_churn_pct"))
        if high_pct is not None and other_pct is not None:
            insight_parts.append(
                f"High-spend short-tenure churn: {high_pct:.2f}% vs {other_pct:.2f}% for other cohorts."
            )
        elif high_pct is not None:
            insight_parts.append(f"High-spend short-tenure churn share: {high_pct:.2f}%.")
        share_pct = self._coerce_float(hint.get("high_spend_short_tenure_share_pct"))
        if share_pct is not None:
            insight_parts.append(f"Segment size: {share_pct:.2f}% of customers.")
        insight = " ".join(insight_parts) or "Correlates total vs monthly charges to spotlight loyalty risks."

        return {
            "id": self._make_section_id("loyalty_scatter"),
            "title": section_title,
            "charts": [
                {
                    "id": chart_id,
                    "type": "scatter",
                    "title": section_title,
                    "insight": insight,
                    "query": {
                        "operation": "scatter",
                        "dataset": self._dataset_name,
                        "x": x_col,
                        "y": y_col,
                        "size": columns.get("size"),
                        "color": columns.get("color"),
                        "text": columns.get("text"),
                        "tooltip_fields": [field for field in (columns.get("size"), columns.get("color")) if field],
                        "options": {"trendline": True, "opacity": 0.85},
                    },
                }
            ],
        }

    def _has_operation(self, plan: Dict[str, Any], operation: str) -> bool:
        for section in plan.get("sections", []) or []:
            for chart in section.get("charts", []) or []:
                query = chart.get("query") or {}
                if isinstance(query, dict) and query.get("operation") == operation:
                    return True
        return False

    def _make_section_id(self, prefix: str) -> str:
        return f"auto-{prefix}-{next(self._id_counter)}"

    def _make_chart_id(self, prefix: str) -> str:
        return f"auto-{prefix}-chart-{next(self._id_counter)}"

    def _column_exists(self, column: Optional[str]) -> bool:
        return bool(column and column in self._column_names)

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def augment_plan(plan: Dict[str, Any], profile_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Functional wrapper so callers don't have to instantiate the class explicitly."""

    return PlanAugmentor(profile_summary).apply(plan)
