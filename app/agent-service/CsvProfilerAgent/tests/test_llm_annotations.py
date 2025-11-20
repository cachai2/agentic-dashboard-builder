"""LLM annotation smoke tests."""

from __future__ import annotations

from pathlib import Path

from app.profiling import profile_csv_path

ROOT = Path(__file__).resolve().parents[1]
TELCO_SAMPLE = ROOT / "samples" / "telco_churn_sample.csv"


def test_telco_profile_emits_annotations() -> None:
    profile = profile_csv_path(TELCO_SAMPLE)
    annotations = profile.llm_annotations

    assert annotations is not None, "Expected llm_annotations block to be populated"
    assert annotations.get("kpis"), "KPI hints should be present"

    funnel = annotations.get("retention_funnel")
    assert funnel is not None and funnel.get("stages"), "Retention funnel should list stages"
    assert any(stage["stage"] == "Churned" for stage in funnel["stages"])

    loyalty_hint = annotations.get("loyalty_hint")
    assert loyalty_hint is not None
    assert loyalty_hint["columns"]["x"] == "MonthlyCharges"
    assert loyalty_hint["columns"]["y"] == "TotalCharges"

    drivers = annotations.get("driver_candidates")
    assert drivers, "Driver candidates help planners pick comparisons"
```}