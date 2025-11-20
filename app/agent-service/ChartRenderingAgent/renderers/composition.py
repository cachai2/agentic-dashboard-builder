"""Stacked composition renderer (area or bar)."""

from __future__ import annotations

from typing import Dict

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.models import CompositionSection
from renderers.base import RenderArtifact, Renderer

PALETTE = ["#2563eb", "#9333ea", "#059669", "#fb923c", "#ec4899"]


class CompositionRenderer(Renderer):
    def render(self, plan_section: CompositionSection, data: pd.DataFrame | None) -> RenderArtifact:
        if data is None:
            raise ValueError("Composition renderer requires a dataset")

        frame = data.copy()
        stacks = plan_section.stacks
        if plan_section.options.normalize:
            totals = frame[stacks].sum(axis=1).replace(0, pd.NA)
            for column in stacks:
                frame[column] = (frame[column] / totals) * 100

        fig = go.Figure()
        if plan_section.options.kind == "stacked_area":
            x_values = frame[plan_section.x.column] if plan_section.x else frame.index
            if plan_section.x and plan_section.x.grain:
                x_values = pd.to_datetime(x_values)
            for idx, column in enumerate(stacks):
                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=frame[column],
                        mode="lines",
                        name=column,
                        stackgroup="one",
                        line=dict(width=0.8, color=PALETTE[idx % len(PALETTE)]),
                    )
                )
        else:
            categories = frame[plan_section.x.column] if plan_section.x else frame.index.astype(str)
            for idx, column in enumerate(stacks):
                fig.add_trace(
                    go.Bar(
                        x=categories,
                        y=frame[column],
                        name=column,
                        marker=dict(color=PALETTE[idx % len(PALETTE)]),
                    )
                )
            fig.update_layout(barmode="stack")

        fig.update_layout(self._layout(plan_section))

        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
        metadata = {
            "operation": plan_section.operation,
            "stacks": stacks,
            "normalize": plan_section.options.normalize,
            "kind": plan_section.options.kind,
        }
        return RenderArtifact(html=html, metadata=metadata)

    def _layout(self, section: CompositionSection) -> Dict[str, object]:
        title = "Percentage" if section.options.normalize else "Value"
        return {
            "height": 360,
            "margin": dict(l=60, r=20, t=20, b=60),
            "template": "plotly_white",
            "legend": dict(orientation="h", y=1.1, x=0),
            "yaxis": dict(title=title + (" (%)" if section.options.normalize else "")),
        }
