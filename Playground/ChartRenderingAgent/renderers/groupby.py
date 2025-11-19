"""Group-by / comparative bar renderer."""

from __future__ import annotations

from typing import Dict

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.models import GroupBySection
from renderers.base import RenderArtifact, Renderer

BAR_COLOR = "#2563eb"
REFERENCE_COLOR = "#94a3b8"


class GroupByRenderer(Renderer):
    def render(self, plan_section: GroupBySection, data: pd.DataFrame | None) -> RenderArtifact:
        if data is None:
            raise ValueError("GroupBy renderer requires a dataset")

        grouped = self._aggregate(data, plan_section)
        orientation = plan_section.options.orientation
        fig = go.Figure()

        if orientation == "vertical":
            fig.add_trace(
                go.Bar(
                    x=grouped[plan_section.dimension],
                    y=grouped["value"],
                    marker=dict(color=BAR_COLOR),
                    text=grouped["value"],
                    textposition="outside",
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    y=grouped[plan_section.dimension],
                    x=grouped["value"],
                    orientation="h",
                    marker=dict(color=BAR_COLOR),
                    text=grouped["value"],
                    textposition="outside",
                )
            )

        if plan_section.options.show_reference:
            ref_value = plan_section.options.reference_value or grouped["value"].mean()
            if orientation == "vertical":
                fig.add_hline(y=ref_value, line_dash="dot", line_color=REFERENCE_COLOR)
            else:
                fig.add_vline(x=ref_value, line_dash="dot", line_color=REFERENCE_COLOR)

        fig.update_layout(self._layout())

        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
        metadata = {
            "operation": plan_section.operation,
            "dimension": plan_section.dimension,
            "metric": plan_section.metric,
            "aggregation": plan_section.aggregation,
            "limit": plan_section.options.limit,
        }
        return RenderArtifact(html=html, metadata=metadata)

    def _aggregate(self, frame: pd.DataFrame, section: GroupBySection) -> pd.DataFrame:
        df = frame.copy()
        agg = section.aggregation
        grouped = df.groupby(section.dimension)[section.metric]
        if agg == "sum":
            series = grouped.sum()
        elif agg in {"avg", "mean"}:
            series = grouped.mean()
        elif agg == "count":
            series = grouped.count()
        else:
            raise ValueError(f"Unsupported aggregation '{agg}'")

        result = series.reset_index().rename(columns={section.metric: "value"})

        if section.options.sort == "desc":
            result = result.sort_values("value", ascending=False)
        elif section.options.sort == "asc":
            result = result.sort_values("value", ascending=True)

        return result.head(section.options.limit)

    def _layout(self) -> Dict[str, object]:
        return {
            "height": 360,
            "margin": dict(l=60, r=40, t=20, b=60),
            "template": "plotly_white",
            "xaxis": dict(showgrid=False),
            "yaxis": dict(showgrid=False),
        }
