"""Render a single chart section using the renderer registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from app.composer import PlanComposer
from app.data_loader import DataCatalog
from app.models import DashboardPlan
from app.toolkit import build_renderer_registry

app = typer.Typer(help="Render an individual chart section from a plan.")


def _load_plan(path: Path) -> DashboardPlan:
    payload = json.loads(path.read_text())
    return DashboardPlan.model_validate(payload)


@app.command()
def render(
    plan: Path = typer.Option(..., exists=True, readable=True, help="Path to dashboard plan JSON."),
    section_index: int = typer.Option(..., help="Zero-based index of the section to render."),
    out: Optional[Path] = typer.Option(None, help="Where to write the HTML fragment."),
    metadata_out: Optional[Path] = typer.Option(None, help="Optional path to dump renderer metadata JSON."),
) -> None:
    dashboard_plan = _load_plan(plan)
    try:
        section = dashboard_plan.sections[section_index]
    except IndexError as exc:
        raise typer.BadParameter(f"Section index {section_index} out of range (total {len(dashboard_plan.sections)}).") from exc

    catalog = DataCatalog(str(plan), dashboard_plan)
    dataset = catalog.load(section.dataset) if getattr(section, "dataset", None) else None

    registry = build_renderer_registry()
    renderer = registry.render(section.operation, section, dataset)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(renderer.html, encoding="utf-8")
        typer.echo(f"Wrote chart HTML to {out}")
    else:
        typer.echo(renderer.html)

    if metadata_out:
        metadata_out.parent.mkdir(parents=True, exist_ok=True)
        metadata_out.write_text(json.dumps(renderer.metadata, indent=2), encoding="utf-8")
        typer.echo(f"Wrote chart metadata to {metadata_out}")


if __name__ == "__main__":  # pragma: no cover
    app()
