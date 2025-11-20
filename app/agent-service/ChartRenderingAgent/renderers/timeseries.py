"""Plotly-based timeseries renderer."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.models import TimeseriesSection
from renderers.base import RenderArtifact, Renderer

PRIMARY_PALETTE = ["#2563eb", "#9333ea", "#fb923c"]
COMPARISON_COLOR = "#94a3b8"
FORECAST_COLOR = "rgba(37, 99, 235, 0.15)"
EVENT_COLOR = "#0f172a"


class TimeseriesRenderer(Renderer):
    def render(self, plan_section: TimeseriesSection, data: pd.DataFrame | None) -> RenderArtifact:
        if data is None:
            raise ValueError("Timeseries renderer requires a dataset")
        frame = data.copy()
        frame[plan_section.x.column] = pd.to_datetime(frame[plan_section.x.column])
        frame.sort_values(plan_section.x.column, inplace=True)

        fig = go.Figure()
        metadata: Dict[str, List[Dict[str, str]]] = {"series": []}
        palette = iter(PRIMARY_PALETTE)

        for series in plan_section.series:
            color = series.style.color if series.style and series.style.color else next(palette, PRIMARY_PALETTE[-1])
            trace = go.Scatter(
                x=frame[plan_section.x.column],
                y=frame[series.column],
                mode="lines",
                name=series.label or series.id,
                line=dict(
                    color=color,
                    dash=(series.style.dash if series.style else None),
                    width=(series.style.width if series.style else 2),
                ),
                hovertemplate="%{y:.2f}<extra>%{fullData.name}</extra>",
                yaxis="y" if series.axis == "primary" else "y2",
            )
            fig.add_trace(trace)
            metadata["series"].append({"id": series.id, "column": series.column, "axis": series.axis})

        if plan_section.forecast:
            self._add_forecast_band(plan_section, frame, fig)
            metadata["forecast"] = plan_section.forecast.model_dump()

        if plan_section.comparison:
            self._add_comparison_trace(plan_section, frame, fig)
            metadata["comparison"] = plan_section.comparison.model_dump()

        if plan_section.events:
            for event in plan_section.events:
                fig.add_vline(x=event.ts, line_dash="dot", line_color=EVENT_COLOR)
                fig.add_annotation(
                    x=event.ts,
                    y=frame[plan_section.series[0].column].max(),
                    text=event.label,
                    showarrow=False,
                    yanchor="bottom",
                    bgcolor="rgba(15, 23, 42, 0.05)",
                )
            metadata["events"] = [event.model_dump() for event in plan_section.events]

        layout = self._build_layout(plan_section)
        fig.update_layout(layout)

        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False, div_id=f"ts-{plan_section.dataset}")
        metadata["axes"] = {
            "x": plan_section.x.model_dump(),
            "y_primary": {"format": plan_section.options.y_axis_format},
            "y_secondary": self._secondary_axis(plan_section),
        }

        return RenderArtifact(html=html, metadata=metadata)

    def _add_forecast_band(self, section: TimeseriesSection, frame: pd.DataFrame, fig: go.Figure) -> None:
        upper = go.Scatter(
            x=frame[section.x.column],
            y=frame[section.forecast.upper],
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
        lower = go.Scatter(
            x=frame[section.x.column],
            y=frame[section.forecast.lower],
            fill="tonexty",
            fillcolor=FORECAST_COLOR,
            line=dict(width=0),
            name=section.forecast.label,
            hovertemplate="Forecast band<extra></extra>",
        )
        fig.add_trace(upper)
        fig.add_trace(lower)

    def _add_comparison_trace(self, section: TimeseriesSection, frame: pd.DataFrame, fig: go.Figure) -> None:
        base_series = section.series[0]
        shifted = frame.copy()
        shifted[section.x.column] = shifted[section.x.column] - pd.to_timedelta(section.comparison.offset_days, unit="d")
        fig.add_trace(
            go.Scatter(
                x=shifted[section.x.column],
                y=shifted[base_series.column],
                mode="lines",
                name=f"{base_series.label or base_series.id} (prev)",
                line=dict(color=COMPARISON_COLOR, dash="dash"),
                hovertemplate="%{y:.2f}<extra>Previous period</extra>",
            )
        )

    def _build_layout(self, section: TimeseriesSection) -> Dict[str, object]:
        compact = section.options.compact
        layout = {
            "height": 360 if not compact else 140,
            "margin": dict(l=48, r=32, t=24, b=48),
            "legend": dict(orientation="h", y=1.12, x=0, bgcolor="rgba(255,255,255,0.6)"),
            "hovermode": "x unified",
            "template": "plotly_white",
            "yaxis": dict(title="", showgrid=not compact, tickformat=self._format_code(section)),
        }
        if any(s.axis == "secondary" for s in section.series):
            layout["yaxis2"] = dict(title="", overlaying="y", side="right", showgrid=False)
        if compact:
            layout["xaxis"] = dict(showgrid=False, showticklabels=False)
            layout["legend"].update(visible=False)
        return layout

    def _format_code(self, section: TimeseriesSection) -> str | None:
        fmt = section.options.y_axis_format
        return {"currency": "$,.2f", "percent": ".1%"}.get(fmt, None)

    def _secondary_axis(self, section: TimeseriesSection):
        if any(s.axis == "secondary" for s in section.series):
            return {"enabled": True}
        return {"enabled": False}
