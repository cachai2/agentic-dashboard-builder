from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from agent_tools import chart_generation_tools as tools

_PLAN_PATH = Path(__file__).parent / "data" / "sample_plan.json"
_SAMPLE_DATASET = Path("sample-data") / "business-insights-sample.csv"

try:  # pragma: no cover - runtime dependency
    import autoviz  # type: ignore  # noqa: F401

    AUTOVIZ_AVAILABLE = True
except ImportError:  # pragma: no cover
    AUTOVIZ_AVAILABLE = False


class ChartGenerationToolsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with _PLAN_PATH.open("r", encoding="utf-8") as handle:
            self.plan = json.load(handle)

    def test_list_chart_adapters(self) -> None:
        result = tools.list_chart_adapters()
        self.assertIn("adapters", result)
        adapter_names = {entry["name"] for entry in result["adapters"]}
        self.assertIn("plotly_express", adapter_names)

    def test_render_dashboard_section_creates_artifact(self) -> None:
        plan_json = json.dumps(self.plan)
        with tempfile.TemporaryDirectory() as tmp_dir:
            response = tools.render_dashboard_section(
                plan_json=plan_json,
                adapter_name="plotly_express",
                output_dir=tmp_dir,
                section_id="revenue_by_region",
            )
            artifact_path = Path(response["artifact_path"])
            self.assertTrue(artifact_path.exists())
            self.assertEqual(response["metadata"]["adapter"], "plotly_express")

    @unittest.skipUnless(AUTOVIZ_AVAILABLE, "AutoViz dependency not installed")
    def test_render_autoviz_dashboard_from_file(self) -> None:
        if not _SAMPLE_DATASET.exists():
            self.skipTest("Sample dataset missing")
        with tempfile.TemporaryDirectory() as tmp_dir:
            response = tools.render_autoviz_dashboard_from_file(
                dataset_path=str(_SAMPLE_DATASET),
                output_dir=tmp_dir,
                max_rows=100,
            )
            artifact_path = Path(response["artifact_path"])
            self.assertTrue(artifact_path.exists())
            self.assertIn("autoviz", artifact_path.name)


if __name__ == "__main__":
    unittest.main()
