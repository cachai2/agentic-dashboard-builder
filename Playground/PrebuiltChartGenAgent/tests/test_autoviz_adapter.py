from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from adapters.autoviz_adapter import AutoVizAdapter

_PLAN_PATH = Path(__file__).parent / "data" / "sample_plan.json"


class AutoVizAdapterTestCase(TestCase):
    def setUp(self) -> None:
        with _PLAN_PATH.open("r", encoding="utf-8") as handle:
            self.plan = json.load(handle)

    def test_render_writes_html(self) -> None:
        section = self.plan["sections"][0]

        class _FakeAutoViz:
            def AutoViz(self, **kwargs: object):  # type: ignore[override]
                save_dir = Path(kwargs["save_plot_dir"]) / "AutoViz"
                save_dir.mkdir(parents=True, exist_ok=True)
                (save_dir / "chart_one.html").write_text("<html><body>chart1</body></html>", encoding="utf-8")
                (save_dir / "chart_two.html").write_text("<html><body>chart2</body></html>", encoding="utf-8")
                return self

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "autoviz.html"
            with patch("adapters.autoviz_adapter.AutoVizAdapter._autoviz_class", return_value=_FakeAutoViz()):
                adapter = AutoVizAdapter(section, output_path=out_file)
                result = adapter.render()
                self.assertTrue(result.artifact_path.exists())
                self.assertEqual(result.metadata["adapter"], AutoVizAdapter.name)
                self.assertIn("rows", result.metadata)
                contents = result.artifact_path.read_text(encoding="utf-8")
                self.assertIn("Chart 1: Chart One", contents)
