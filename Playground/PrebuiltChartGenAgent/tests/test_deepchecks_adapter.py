from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from adapters.deepchecks_adapter import DeepchecksAdapter

_PLAN_PATH = Path(__file__).parent / "data" / "sample_plan.json"


class DeepchecksAdapterTestCase(TestCase):
    def setUp(self) -> None:
        with _PLAN_PATH.open("r", encoding="utf-8") as handle:
            self.plan = json.load(handle)

    def test_render_uses_suite_result(self) -> None:
        section = self.plan["sections"][1]

        class _FakeResult:
            def __init__(self) -> None:
                self.results = [self._fake_check(False), self._fake_check(True)]

            @staticmethod
            def _fake_check(passed: bool):
                class _Condition:
                    condition_passed = passed

                class _Check:
                    conditions_results = [_Condition()]

                return _Check()

            def save_as_html(self, path: str) -> None:
                Path(path).write_text("<html></html>", encoding="utf-8")

        class _FakeSuite:
            def run(self, dataset):
                self.dataset = dataset
                return _FakeResult()

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "deepchecks.html"
            with patch("adapters.deepchecks_adapter.DeepchecksAdapter._build_dc_dataset", return_value=object()), patch(
                "adapters.deepchecks_adapter.DeepchecksAdapter._load_suite",
                return_value=(_FakeSuite(), "data_integrity"),
            ):
                adapter = DeepchecksAdapter(section, output_path=out_file)
                result = adapter.render()
                self.assertTrue(result.artifact_path.exists())
                self.assertEqual(result.metadata["failed_checks"], 1)
