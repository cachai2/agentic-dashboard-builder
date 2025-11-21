from __future__ import annotations

from pathlib import Path

import pytest  # type: ignore

from agent_orchestrator.settings import get_settings
from agent_orchestrator.workflows import UploadToDashboardWorkflow

TELCO_SAMPLE = Path(__file__).resolve().parents[2] / "CsvProfilerAgent" / "samples" / "telco_churn_sample.csv"


def _find_section(sections: list[dict], title: str) -> dict:
    for section in sections:
        if section.get("title") == title:
            return section
    raise AssertionError(f"section '{title}' not found in plan")


@pytest.mark.integration
def test_telco_churn_happy_path() -> None:
    assert TELCO_SAMPLE.exists(), "telco sample CSV is missing from the repo"

    workflow = UploadToDashboardWorkflow()
    session_id = "test-telco-happy-path"
    execution = workflow.run_with_events(
        csv_path=TELCO_SAMPLE,
        dataset_name="telco_churn_sample",
        session_id=session_id,
    )

    events = execution.events
    result = execution.result
    profile = result.profile
    plan_bundle = result.plan

    assert any(
        event.type == "ExecutorInvokedEvent" and event.payload.get("executorId") == "profile_executor"
        for event in events
    ), "profile executor never started"
    assert any(
        event.type == "ExecutorInvokedEvent" and event.payload.get("executorId") == "planner_executor"
        for event in events
    ), "planner executor never started"
    output_event = next(event for event in events if event.type == "WorkflowOutputEvent")
    assert output_event.payload.get("sourceExecutorId") == "planner_executor"

    assert profile["dataset_name"] == "telco_churn_sample"
    assert profile["row_count"] >= 5000
    assert profile["sampled_row_count"] == get_settings().csv_profiler_max_rows
    assert len(profile["columns"]) >= 20

    assert plan_bundle is not None, "planner did not return a payload"
    plan = plan_bundle["plan"]
    metadata = plan_bundle["metadata"]
    assert metadata["session_id"] == session_id
    assert metadata["prompt_version"] == get_settings().prompt_version
    assert plan["sections"]

    annotations = profile.get("llm_annotations")
    assert annotations is not None, "profiler did not produce annotations"

    kpi_lookup = {entry["label"]: entry for entry in annotations["kpis"]}
    kpi_section = _find_section(plan["sections"], "Customer Snapshot")
    kpi_cards = kpi_section["charts"][0]["query"]["cards"]
    for card in kpi_cards:
        source = kpi_lookup[card["title"]]
        expected_value = source.get("value")
        if expected_value is None:
            expected_value = source.get("value_pct")
        assert expected_value is not None
        assert pytest.approx(card["value"], rel=1e-3) == pytest.approx(expected_value, rel=1e-3)

    funnel_section = _find_section(plan["sections"], "Retention Funnel")
    funnel_chart = funnel_section["charts"][0]
    plan_stages = [stage["stage"] for stage in funnel_chart["query"]["data"]]
    profile_stages = [stage["stage"] for stage in annotations["retention_funnel"]["stages"]]
    assert plan_stages == profile_stages

    loyalty_section = _find_section(plan["sections"], "Loyalty vs Spend")
    loyalty_chart = loyalty_section["charts"][0]
    assert loyalty_chart["query"]["dataset"] == profile["dataset_name"]
