"""KPI tile renderer."""

from __future__ import annotations

import html
from typing import Dict, List

import pandas as pd  # pragma: no cover - satisfies interface typing

from app.models import KPISection, KpiCard
from renderers.base import RenderArtifact, Renderer

STYLE_BLOCK = """
<style>
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.kpi-row { display: flex; gap: 12px; overflow-x: auto; }
.kpi-card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; background: #fff; box-shadow: 0 1px 3px rgba(15,23,42,0.08); min-width: 160px; }
.kpi-title { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin: 0 0 8px; }
.kpi-value { font-size: 1.4rem; font-weight: 600; margin: 0; }
.kpi-delta { font-size: 0.85rem; margin-top: 4px; color: #475569; }
.kpi-spark { margin-top: 8px; }
</style>
"""


class KpiRenderer(Renderer):
    def render(self, plan_section: KPISection, data: pd.DataFrame | None) -> RenderArtifact:  # noqa: ARG002 - interface
        wrapper_class = "kpi-grid" if plan_section.layout == "grid" else "kpi-row"
        cards_html = "".join(self._card_markup(card) for card in plan_section.cards)
        html_output = f"{STYLE_BLOCK}<div class=\"{wrapper_class}\">{cards_html}</div>"
        metadata = {
            "operation": plan_section.operation,
            "card_count": len(plan_section.cards),
            "layout": plan_section.layout,
            "cards": [self._card_meta(card) for card in plan_section.cards],
        }
        return RenderArtifact(html=html_output, metadata=metadata)

    def _card_markup(self, card: KpiCard) -> str:
        value = html.escape(f"{card.value:,.2f}" if isinstance(card.value, (int, float)) else str(card.value))
        unit = html.escape(card.unit) + " " if card.unit else ""
        delta = self._delta_text(card)
        sparkline = self._sparkline(card.trend) if card.trend else ""
        body = (
            f"<p class=\"kpi-title\">{html.escape(card.title)}</p>"
            f"<p class=\"kpi-value\">{unit}{value}</p>"
            f"{delta}"
            f"{sparkline}"
        )
        return f"<div class=\"kpi-card\">{body}</div>"

    def _delta_text(self, card: KpiCard) -> str:
        if not card.delta:
            return ""
        prefix = {"up": "+", "down": "-", "flat": ""}.get(card.delta.direction, "")
        label = card.delta.label or "vs prior"
        value = f"{prefix}{card.delta.value:.2%}" if isinstance(card.delta.value, float) else str(card.delta.value)
        return f"<div class=\"kpi-delta\">{value} {html.escape(label)}</div>"

    def _sparkline(self, points: List[float]) -> str:
        if not points:
            return ""
        width, height = 120, 36
        min_val = min(points)
        max_val = max(points)
        span = max(max_val - min_val, 1e-6)
        step = width / max(len(points) - 1, 1)
        coords = []
        for idx, value in enumerate(points):
            x = idx * step
            y = height - ((value - min_val) / span) * height
            coords.append(f"{x:.2f},{y:.2f}")
        polyline = " ".join(coords)
        return (
            f"<svg class=\"kpi-spark\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\" role=\"img\">"
            f"<polyline fill=\"none\" stroke=\"#2563eb\" stroke-width=\"2\" points=\"{polyline}\" /></svg>"
        )

    def _card_meta(self, card: KpiCard) -> Dict[str, object]:
        return {
            "title": card.title,
            "value": card.value,
            "delta": card.delta.model_dump() if card.delta else None,
            "trend_points": len(card.trend),
        }
