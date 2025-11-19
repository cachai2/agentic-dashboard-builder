from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from adapters.plotly_express_adapter import PlotlyExpressAdapter

_PLAN_PATH = Path(__file__).parent / "data" / "sample_plan.json"


class PlotlyAdapterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with _PLAN_PATH.open("r", encoding="utf-8") as handle:
            self.plan = json.load(handle)

    def test_render_first_section(self) -> None:
        section = self.plan["sections"][0]
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "plotly_test.html"
            adapter = PlotlyExpressAdapter(section, output_path=out_file)
            result = adapter.render()
            self.assertTrue(result.artifact_path.exists())
            self.assertEqual(result.metadata["adapter"], PlotlyExpressAdapter.name)


if __name__ == "__main__":
    unittest.main()
