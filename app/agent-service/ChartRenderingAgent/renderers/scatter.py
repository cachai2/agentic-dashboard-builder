"""Correlation / bubble scatter renderer."""

from __future__ import annotations

from typing import List, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.models import ScatterSection
from renderers.base import RenderArtifact, Renderer

PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#f97316", "#7c3aed", "#0ea5e9"]
DEFAULT_MARKER_SIZE = 18
BUBBLE_MIN_SIZE = 12.0
BUBBLE_MAX_SIZE = 42.0


class ScatterRenderer(Renderer):
    def render(self, plan_section: ScatterSection, data: pd.DataFrame | None) -> RenderArtifact:
        if data is None:
            raise ValueError("Scatter renderer requires a dataset")

        frame = data.copy()
        fig = go.Figure()

        groups = self._group_by_color(frame, plan_section)
        tooltip_fields = self._collect_tooltip_fields(plan_section)
        hover_template = self._hover_template(plan_section, tooltip_fields)

        for idx, (group_name, subset) in enumerate(groups):
            if subset.empty:
                continue

            marker_sizes = (
                self._scale_sizes(subset[plan_section.size])
                if plan_section.size
                else DEFAULT_MARKER_SIZE
            )

            trace_kwargs: dict = dict(
                x=subset[plan_section.x],
                y=subset[plan_section.y],
                mode="markers+text" if plan_section.text else "markers",
                name=group_name,
                text=subset[plan_section.text] if plan_section.text else None,
                textposition="top center",
                marker=dict(
                    size=marker_sizes,
                    color=PALETTE[idx % len(PALETTE)],
                    opacity=plan_section.options.opacity,
                    line=dict(color="#ffffff", width=1),
                ),
                hovertemplate=hover_template,
            )

            if tooltip_fields:
                trace_kwargs["customdata"] = subset[tooltip_fields].to_numpy()

            fig.add_trace(go.Scatter(**trace_kwargs))

        if plan_section.options.trendline:
            self._add_trendline(fig, frame, plan_section)

        if plan_section.quadrant:
            self._add_quadrants(fig, frame, plan_section)

        fig.update_layout(self._layout(plan_section))

        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
        metadata = {
            "operation": plan_section.operation,
            "points": len(frame),
            "uses_size": plan_section.size is not None,
            "uses_color": plan_section.color is not None,
            "trendline": bool(plan_section.options.trendline),
            "quadrant": plan_section.quadrant is not None,
        }
        return RenderArtifact(html=html, metadata=metadata)

    def _group_by_color(
        self, frame: pd.DataFrame, plan_section: ScatterSection
    ) -> List[tuple[str, pd.DataFrame]]:
        if not plan_section.color:
            label = plan_section.title or plan_section.operation
            return [(label, frame)]

        color_series = frame[plan_section.color].fillna("Other")
        groups: List[tuple[str, pd.DataFrame]] = []
        for key, subset in frame.groupby(color_series):
            groups.append((str(key), subset))
        return groups

    def _collect_tooltip_fields(self, section: ScatterSection) -> List[str]:
        ordered: List[str] = []
        if section.size:
            ordered.append(section.size)
        for field in section.tooltip_fields:
            if field not in ordered:
                ordered.append(field)
        return ordered

    def _hover_template(self, section: ScatterSection, fields: Sequence[str]) -> str:
        lines = [f"{section.x}: %{{x}}", f"{section.y}: %{{y}}"]
        for idx, field in enumerate(fields):
            lines.append(f"{field}: %{{customdata[{idx}]}}")
        return "<br>".join(lines) + "<extra></extra>"

    def _scale_sizes(self, series: pd.Series) -> List[float]:
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.empty:
            return []
        median = numeric.median()
        if pd.isna(median):
            median = 1.0
        values = numeric.fillna(median)
        vmin, vmax = values.min(), values.max()
        if vmin == vmax:
            midpoint = (BUBBLE_MAX_SIZE + BUBBLE_MIN_SIZE) / 2
            return [midpoint] * len(values)
        scaled = (values - vmin) / (vmax - vmin)
        return (scaled * (BUBBLE_MAX_SIZE - BUBBLE_MIN_SIZE) + BUBBLE_MIN_SIZE).tolist()

    def _add_trendline(self, fig: go.Figure, frame: pd.DataFrame, section: ScatterSection) -> None:
        x = pd.to_numeric(frame[section.x], errors="coerce")
        y = pd.to_numeric(frame[section.y], errors="coerce")
        mask = x.notna() & y.notna()
        if mask.sum() < 2:
            return
        x_clean = x[mask]
        y_clean = y[mask]
        coeffs = np.polyfit(x_clean, y_clean, deg=1)
        x_range = np.linspace(x_clean.min(), x_clean.max(), num=50)
        y_pred = coeffs[0] * x_range + coeffs[1]
        fig.add_trace(
            go.Scatter(
                x=x_range,
                y=y_pred,
                mode="lines",
                name="Trendline",
                line=dict(color="#475569", dash="dot"),
                hoverinfo="skip",
                showlegend=True,
            )
        )

    def _add_quadrants(
        self, fig: go.Figure, frame: pd.DataFrame, section: ScatterSection
    ) -> None:
        quadrant = section.quadrant
        if quadrant is None:
            return
        fig.add_vline(x=quadrant.x, line=dict(color="#94a3b8", width=1, dash="dash"))
        fig.add_hline(y=quadrant.y, line=dict(color="#94a3b8", width=1, dash="dash"))

        if not quadrant.labels:
            return

        x_min, x_max = frame[section.x].min(), frame[section.x].max()
        y_min, y_max = frame[section.y].min(), frame[section.y].max()
        positions = [
            ((x_min + quadrant.x) / 2, (y_min + quadrant.y) / 2),
            ((quadrant.x + x_max) / 2, (y_min + quadrant.y) / 2),
            ((x_min + quadrant.x) / 2, (quadrant.y + y_max) / 2),
            ((quadrant.x + x_max) / 2, (quadrant.y + y_max) / 2),
        ]
        for label, (x_pos, y_pos) in zip(quadrant.labels, positions):
            fig.add_annotation(
                x=x_pos,
                y=y_pos,
                text=label,
                showarrow=False,
                font=dict(color="#475569", size=12),
                bgcolor="rgba(255,255,255,0.7)",
            )

    def _layout(self, section: ScatterSection) -> dict:
        return {
            "height": 420,
            "template": "plotly_white",
            "margin": dict(l=60, r=20, t=30, b=60),
            "legend": dict(orientation="h", y=1.02, x=0),
            "xaxis": dict(title=section.x, zeroline=False),
            "yaxis": dict(title=section.y, zeroline=False),
        }
