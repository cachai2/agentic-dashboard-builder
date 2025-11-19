"""Command line entrypoint for the chart rendering agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from app.composer import PlanComposer
from app.models import DashboardPlan
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

app = typer.Typer(help="Render dashboard plans into embeddable HTML.")


def _load_plan(path: Path) -> DashboardPlan:
    payload = json.loads(path.read_text())
    return DashboardPlan.model_validate(payload)


def _build_registry() -> RendererRegistry:
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


@app.command()
def render(plan: Path = typer.Option(..., exists=True, readable=True), out: Optional[Path] = typer.Option(None)) -> None:
    """Render a dashboard plan. Writes to --out or stdout."""

    dashboard_plan = _load_plan(plan)
    composer = PlanComposer(_build_registry())
    artifact = composer.render_plan(str(plan), dashboard_plan)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(artifact.html, encoding="utf-8")
        typer.echo(f"Wrote HTML to {out}")
    else:
        typer.echo(artifact.html)


if __name__ == "__main__":  # pragma: no cover
    app()
