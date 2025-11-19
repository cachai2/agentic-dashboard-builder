"""CLI tool that composes an entire dashboard plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from app.composer import PlanComposer
from app.models import DashboardPlan
from app.toolkit import build_renderer_registry

app = typer.Typer(help="Render dashboard plans into embeddable HTML.")


def _load_plan(path: Path) -> DashboardPlan:
    payload = json.loads(path.read_text())
    return DashboardPlan.model_validate(payload)


@app.command()
def render(plan: Path = typer.Option(..., exists=True, readable=True), out: Optional[Path] = typer.Option(None)) -> None:
    """Render a dashboard plan. Writes to --out or stdout."""

    dashboard_plan = _load_plan(plan)
    composer = PlanComposer(build_renderer_registry())
    artifact = composer.render_plan(str(plan), dashboard_plan)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(artifact.html, encoding="utf-8")
        typer.echo(f"Wrote HTML to {out}")
    else:
        typer.echo(artifact.html)


if __name__ == "__main__":  # pragma: no cover
    app()
