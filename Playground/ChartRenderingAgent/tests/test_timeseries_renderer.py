"""Renderer integration sanity checks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.models import DashboardPlan
from renderers import (
    AnomalyRenderer,
    CompositionRenderer,
    DistributionRenderer,
    GroupByRenderer,
    KpiRenderer,
    TimeseriesRenderer,
)

FIXTURE_DIR = Path(__file__).parent / "data"
PROJECT_ROOT = Path(__file__).parent.parent


def load_plan(name: str = "sample_plan.json") -> DashboardPlan:
    return DashboardPlan.model_validate_json((FIXTURE_DIR / name).read_text())


def load_dataset(plan: DashboardPlan, dataset_id: str):
    cfg = plan.dataset_by_id(dataset_id)
    return pd.read_csv(PROJECT_ROOT / cfg.path)


def test_timeseries_renderer_outputs_html():
    plan = load_plan()
    section = next(sec for sec in plan.sections if sec.operation == "timeseries")
    renderer = TimeseriesRenderer()
    df = load_dataset(plan, section.dataset)
    artifact = renderer.render(section, df)

    assert "plotly" in artifact.html
    assert artifact.metadata["series"][0]["id"] == "actual"
    assert artifact.metadata["comparison"]["mode"] == "previous_period"


def test_groupby_renderer_outputs_html():
    plan = load_plan()
    section = next(sec for sec in plan.sections if sec.operation == "groupby")
    renderer = GroupByRenderer()
    df = load_dataset(plan, section.dataset)
    artifact = renderer.render(section, df)

    assert "plotly" in artifact.html
    assert artifact.metadata["metric"] == "revenue"


def test_composition_renderer_outputs_html():
    plan = load_plan()
    section = next(sec for sec in plan.sections if sec.operation == "composition")
    renderer = CompositionRenderer()
    df = load_dataset(plan, section.dataset)
    artifact = renderer.render(section, df)

    assert "plotly" in artifact.html
    assert artifact.metadata["normalize"] is True


def test_distribution_renderer_outputs_html():
    plan = load_plan()
    section = next(sec for sec in plan.sections if sec.operation == "distribution")
    renderer = DistributionRenderer()
    df = load_dataset(plan, section.dataset)
    artifact = renderer.render(section, df)

    assert "plotly" in artifact.html
    assert artifact.metadata["stats"]["count"] > 0


def test_anomaly_renderer_outputs_html():
    plan = load_plan()
    section = next(sec for sec in plan.sections if sec.operation == "outliers")
    renderer = AnomalyRenderer()
    df = load_dataset(plan, section.dataset)
    artifact = renderer.render(section, df)

    assert "plotly" in artifact.html
    assert artifact.metadata["anomaly_count"] >= 1


def test_kpi_renderer_outputs_html():
    plan = load_plan()
    section = next(sec for sec in plan.sections if sec.operation == "kpi")
    renderer = KpiRenderer()
    artifact = renderer.render(section, data=None)

    assert "kpi-card" in artifact.html
    assert artifact.metadata["card_count"] == len(section.cards)
