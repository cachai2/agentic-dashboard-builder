import copy

from ollama_proxy_service.app.augmentations import augment_plan


def _base_profile():
    return {
        "dataset_name": "uploaded_dataset",
        "columns": [
            {"name": "tenure"},
            {"name": "monthly_charges"},
        ],
        "llm_annotations": {
            "kpis": [
                {"label": "Churn Rate", "value_pct": 28.3},
                {"label": "Fiber Customers", "value": 4300, "unit": "accounts"},
            ],
            "retention_funnel": {
                "stages": [
                    {"stage": "All Customers", "count": 10000},
                    {"stage": "Tenure > 1y", "count": 5800},
                    {"stage": "Churned", "count": 2600},
                ]
            },
            "loyalty_hint": {
                "columns": {"x": "tenure", "y": "monthly_charges"},
                "high_spend_short_tenure_churn_pct": 64.2,
                "other_segments_churn_pct": 23.1,
            },
        },
    }


def _base_plan():
    return {
        "title": "Demo Plan",
        "description": "Test plan",
        "sections": [
            {
                "id": "section-1",
                "title": "Existing",
                "charts": [
                    {
                        "id": "chart-1",
                        "type": "groupby",
                        "query": {"operation": "groupby_agg", "x": "tenure", "y": "monthly_charges"},
                    }
                ],
            }
        ],
    }


def test_augment_plan_injects_annotation_driven_charts():
    profile = _base_profile()
    plan = _base_plan()
    augmented = augment_plan(copy.deepcopy(plan), profile)

    operations = [chart.get("query", {}).get("operation") for section in augmented["sections"] for chart in section.get("charts", [])]
    assert "kpi" in operations
    assert "funnel" in operations
    assert "scatter" in operations
    # New sections should prepend existing ones to highlight deterministic context
    assert augmented["sections"][0]["charts"][0]["query"]["operation"] == "kpi"


def test_augment_plan_skips_when_annotations_missing():
    profile = {"dataset_name": "uploaded_dataset", "columns": []}
    plan = _base_plan()
    augmented = augment_plan(copy.deepcopy(plan), profile)
    operations = [chart.get("query", {}).get("operation") for section in augmented["sections"] for chart in section.get("charts", [])]
    assert operations.count("kpi") == 0
    assert operations.count("funnel") == 0
    assert operations.count("scatter") == 0
