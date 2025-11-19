"""Funnel renderer for conversion pipelines."""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.models import FunnelSection
from renderers.base import RenderArtifact, Renderer

PALETTE = ["#0ea5e9", "#6366f1", "#22c55e", "#f97316", "#f43f5e", "#8b5cf6"]


def _order_stages(frame: pd.DataFrame, stages: List[str], column: str) -> pd.DataFrame:
    if not stages:
        return frame
    ordered = pd.Categorical(frame[column], categories=stages, ordered=True)
    return frame.assign(**{column: ordered}).sort_values(column)


class FunnelRenderer(Renderer):
    def render(self, plan_section: FunnelSection, data: pd.DataFrame | None) -> RenderArtifact:
        if data is None:
            raise ValueError("Funnel renderer requires a dataset")

        frame = data.copy()
        frame = _order_stages(frame, plan_section.stages, plan_section.stage_column)
        stages = frame[plan_section.stage_column].astype(str).tolist()
        values = frame[plan_section.value_column].astype(float).tolist()

        textinfo_parts = ["value"]
        if plan_section.options.show_conversion:
            textinfo_parts.extend(["percent previous", "percent initial"])
        else:
            textinfo_parts.append("label")

        comparison_text = None
        if plan_section.options.show_delta and plan_section.comparison_column:
            comparison_values = frame[plan_section.comparison_column].astype(float).tolist()
            comparison_text = [
                self._format_delta(current, previous)
                for current, previous in zip(values, comparison_values)
            ]

        fig = go.Figure(
            go.Funnel(
                y=stages,
                x=values,
                text=comparison_text,
                textposition="inside",
                textinfo="+".join(dict.fromkeys(textinfo_parts)),
                opacity=0.9,
                marker=dict(
                    color=[PALETTE[idx % len(PALETTE)] for idx in range(len(stages))],
                    line=dict(color="#ffffff", width=1),
                ),
            )
        )

        fig.update_layout(
            template="plotly_white",
            margin=dict(l=80, r=80, t=40, b=20),
            height=420,
        )

        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
        metadata = {
            "operation": plan_section.operation,
            "stage_count": len(stages),
            "show_conversion": plan_section.options.show_conversion,
            "show_delta": plan_section.options.show_delta and bool(plan_section.comparison_column),
        }
        return RenderArtifact(html=html, metadata=metadata)

    def _format_delta(self, current: float, previous: float) -> str:
        if np.isnan(previous) or previous == 0:
            return ""
        delta = (current - previous) / previous * 100
        return f"{delta:+.1f}% vs prev"
