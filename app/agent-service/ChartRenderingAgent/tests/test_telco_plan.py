from pathlib import Path

from app.composer import PlanComposer
from app.models import DashboardPlan
from app.toolkit import build_renderer_registry


def test_telco_dashboard_plan_renders(tmp_path):
    root = Path(__file__).resolve().parents[1]
    plan_path = root / "samples" / "telco_dashboard_plan.json"
    dashboard_plan = DashboardPlan.model_validate_json(plan_path.read_text())

    composer = PlanComposer(build_renderer_registry())
    artifact = composer.render_plan(str(plan_path), dashboard_plan)

    out_file = tmp_path / "telco_dashboard.html"
    out_file.write_text(artifact.html, encoding="utf-8")

    assert "Telco Snapshot" in artifact.html
    assert "Active Customers vs Churn Rate" in artifact.html
    assert out_file.exists()
