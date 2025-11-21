"""Render a dashboard HTML artifact from a dataset + planner payload."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from agent_orchestrator.runtime.dashboard_renderer import DashboardRenderer

app = typer.Typer(help="Render the planner output into a single HTML dashboard artifact.")


def _load_plan(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@app.command()
def render(
    dataset: Path = typer.Option(..., exists=True, readable=True, help="CSV dataset used during profiling."),
    plan: Path = typer.Option(..., exists=True, readable=True, help="Planner payload JSON (plan.json)."),
    out: Path = typer.Option(..., help="Destination HTML path (directories auto-created)."),
) -> None:
    renderer = DashboardRenderer()
    payload = _load_plan(plan)
    artifact = renderer.render(dataset, payload)
    if artifact is None:
        raise typer.BadParameter("Dashboard renderer unavailable or plan produced no renderable charts.")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(artifact.html, encoding="utf-8")
    typer.echo(f"Dashboard HTML written to {out}")


if __name__ == "__main__":  # pragma: no cover
    app()
