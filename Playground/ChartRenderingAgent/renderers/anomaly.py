"""Anomaly and outlier renderer."""

from __future__ import annotations

from typing import Dict

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from app.models import AnomalySection
from renderers.base import RenderArtifact, Renderer

BASE_COLOR = "#0ea5e9"
ANOMALY_COLOR = "#dc2626"
THRESHOLD_COLOR = "#f97316"
EVENT_COLOR = "#334155"


class AnomalyRenderer(Renderer):
    def render(self, plan_section: AnomalySection, data: pd.DataFrame | None) -> RenderArtifact:
        if data is None:
            raise ValueError("Anomaly renderer requires a dataset")

        frame = data.copy()
        frame[plan_section.x.column] = pd.to_datetime(frame[plan_section.x.column])
        frame.sort_values(plan_section.x.column, inplace=True)
        anomalies_mask = self._find_anomalies(frame, plan_section)

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=frame[plan_section.x.column],
                y=frame[plan_section.y],
                mode="lines+markers",
                name=plan_section.y,
                line=dict(color=BASE_COLOR, width=2),
                hovertemplate="%{y:.2f}<extra></extra>",
            )
        )

        if anomalies_mask.any():
            fig.add_trace(
                go.Scatter(
                    x=frame.loc[anomalies_mask, plan_section.x.column],
                    y=frame.loc[anomalies_mask, plan_section.y],
                    mode="markers",
                    name="Anomaly",
                    marker=dict(color=ANOMALY_COLOR, size=10, symbol="circle-open-dot"),
                    hovertemplate="Anomaly: %{y:.2f}<extra></extra>",
                )
            )

        if plan_section.threshold:
            value = plan_section.threshold.value
            fig.add_hline(y=value, line_dash="dash", line_color=THRESHOLD_COLOR)

        if plan_section.events:
            for event in plan_section.events:
                fig.add_vline(x=event.ts, line_dash="dot", line_color=EVENT_COLOR)
                fig.add_annotation(
                    x=event.ts,
                    y=frame[plan_section.y].max(),
                    text=event.label,
                    showarrow=False,
                    yanchor="bottom",
                    bgcolor="rgba(51,65,85,0.08)",
                )

        fig.update_layout(self._layout())

        html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False)
        metadata = {
            "operation": plan_section.operation,
            "y": plan_section.y,
            "threshold": plan_section.threshold.model_dump() if plan_section.threshold else None,
            "anomaly_count": int(anomalies_mask.sum()),
        }
        return RenderArtifact(html=html, metadata=metadata)

    def _find_anomalies(self, frame: pd.DataFrame, section: AnomalySection) -> pd.Series:
        if section.flag_column and section.flag_column in frame:
            return frame[section.flag_column].astype(bool)
        if section.threshold:
            if section.threshold.direction == "above":
                return frame[section.y] >= section.threshold.value
            return frame[section.y] <= section.threshold.value
        return pd.Series(False, index=frame.index)

    def _layout(self) -> Dict[str, object]:
        return {
            "height": 360,
            "margin": dict(l=60, r=20, t=20, b=60),
            "template": "plotly_white",
            "hovermode": "x unified",
        }
