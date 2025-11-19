"""Generate Deepchecks reports for DashboardPlan sections."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .base import AdapterResult, BaseAdapter
from .utils import dataset_to_dataframe


class DeepchecksAdapter(BaseAdapter):
    name = "deepchecks"

    def render(self) -> AdapterResult:
        section = self._validated_section(self.section)
        dataframe = dataset_to_dataframe(section["dataset"])
        output_path = self._validated_output_path(self.output_path)

        dataset = self._build_dc_dataset(dataframe, section.get("encodings", {}))
        suite, suite_name = self._load_suite(section)
        result = suite.run(dataset)
        result.save_as_html(str(output_path))

        metadata = {
            "adapter": self.name,
            "suite": suite_name,
            "rows": len(dataframe),
            "columns": list(dataframe.columns),
            "failed_checks": self._failed_checks_count(result),
        }
        return AdapterResult(output_path, metadata)

    @staticmethod
    def _build_dc_dataset(dataframe: pd.DataFrame, encodings: Mapping[str, Any]):
        label_name = encodings.get("y")
        label = None
        features = dataframe.copy()

        if label_name and label_name in dataframe.columns:
            label = dataframe[label_name]
            if len(dataframe.columns) > 1:
                features = dataframe.drop(columns=[label_name])

        categorical_features = [
            col for col in features.columns if pd.api.types.is_object_dtype(features[col])
        ]

        try:
            from deepchecks.tabular import Dataset
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Deepchecks dependency missing. Run 'pip install deepchecks' to enable this adapter."
            ) from exc

        return Dataset(
            features,
            label=label,
            label_name=label_name,
            cat_features=categorical_features or None,
        )

    @staticmethod
    def _load_suite(section: Mapping[str, Any]):
        suite_name = section.get("suite", "data_integrity")
        try:
            from deepchecks.tabular.suites import (
                data_integrity,
                model_evaluation,
                train_test_validation,
            )
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Deepchecks dependency missing. Run 'pip install deepchecks' to enable this adapter."
            ) from exc

        suites = {
            "data_integrity": data_integrity,
            "model_evaluation": model_evaluation,
            "train_test_validation": train_test_validation,
        }
        suite_factory = suites.get(suite_name)
        if suite_factory is None:
            valid = ", ".join(sorted(suites))
            raise ValueError(f"Unsupported Deepchecks suite '{suite_name}'. Valid options: {valid}")
        return suite_factory(), suite_name

    @staticmethod
    def _failed_checks_count(result: Any) -> int:
        failed = 0
        for check_result in getattr(result, "results", []):
            conditions = getattr(check_result, "conditions_results", [])
            if any(getattr(cond, "condition_passed", True) is False for cond in conditions):
                failed += 1
        return failed

    @staticmethod
    def _validated_section(section: Mapping[str, Any]) -> Mapping[str, Any]:
        if "dataset" not in section:
            raise ValueError("DashboardPlan section must include a 'dataset' block.")
        return section

    @staticmethod
    def _validated_output_path(path: Path) -> Path:
        suffix = path.suffix.lower()
        if suffix not in {".html", ".htm"}:
            raise ValueError("Deepchecks adapter only supports HTML artifacts.")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
