"""Shared helpers for tool-oriented entrypoints."""

from __future__ import annotations

from app.registry import RendererRegistry
from renderers import (
    AnomalyRenderer,
    CompositionRenderer,
    DistributionRenderer,
    FunnelRenderer,
    GroupByRenderer,
    KpiRenderer,
    ScatterRenderer,
    TimeseriesRenderer,
)


def build_renderer_registry() -> RendererRegistry:
    registry = RendererRegistry()
    registry.register("timeseries", TimeseriesRenderer())
    registry.register("groupby", GroupByRenderer())
    registry.register("composition", CompositionRenderer())
    registry.register("distribution", DistributionRenderer())
    registry.register("outliers", AnomalyRenderer())
    registry.register("kpi", KpiRenderer())
    registry.register("scatter", ScatterRenderer())
    registry.register("funnel", FunnelRenderer())
    return registry
