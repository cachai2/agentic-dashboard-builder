"""Distribution / histogram renderer."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.models import DistributionSection
from renderers.base import RenderArtifact, Renderer

BASE_COLOR = "#9333ea"
DENSITY_COLOR = "#0f172a"


class DistributionRenderer(Renderer):
    def render(self, plan_section: DistributionSection, data: pd.DataFrame | None) -> RenderArtifact:
        if data is None:
            raise ValueError("Distribution renderer requires a dataset")

        values = data[plan_section.metric].dropna()
        fig = go.Figure()
        fig.add_trace(
            go.Histogram(
                x=values,
                marker=dict(color=BASE_COLOR, opacity=0.65),
                nbinsx=plan_section.options.bins,
                name=plan_section.metric,
                hovertemplate="%{x}<extra>Count: %{y}</extra>",
            )
        )

        density_trace = self._density_trace(values, plan_section)
        if density_trace:
            fig.add_trace(density_trace)

        if plan_section.options.show_boxplot:
            fig.add_trace(
                go.Box(
                    x=values,
                    name="Spread",
                    marker_color=DENSITY_COLOR,
                    boxpoints=False,
                    orientation="h",
                    hoverinfo="skip",
                )
            )

        stats = {
            "count": int(values.count()),
            "mean": float(values.mean()),
            "median": float(values.median()),
            "std": float(values.std(ddof=0)),
        }
        fig.update_layout(self._layout(plan_section))

        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
        metadata = {
            "operation": plan_section.operation,
            "metric": plan_section.metric,
            "bins": plan_section.options.bins,
            "stats": stats,
        }
        return RenderArtifact(html=html, metadata=metadata)

    def _density_trace(self, values: pd.Series, section: DistributionSection):
        if section.options.overlay != "density":
            return None
        counts, bin_edges = np.histogram(values, bins=section.options.bins, density=True)
        centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        return go.Scatter(
            x=centers,
            y=counts,
            name="Density",
            line=dict(color=DENSITY_COLOR, width=2),
            hovertemplate="Density: %{y:.3f}<extra></extra>",
        )

    def _layout(self, section: DistributionSection) -> Dict[str, object]:
        return {
            "height": 360,
            "margin": dict(l=60, r=20, t=20, b=60),
            "template": "plotly_white",
            "barmode": "overlay",
            "legend": dict(orientation="h", y=1.05, x=0),
            "xaxis": dict(title=section.metric),
            "yaxis": dict(title="Count"),
        }
