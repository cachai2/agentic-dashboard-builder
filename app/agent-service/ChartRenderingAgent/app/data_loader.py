"""Helpers to materialize plan datasets into pandas DataFrames."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

from .models import DashboardPlan


class DataCatalog:
    """Loads and caches datasets defined inside a `DashboardPlan`."""

    def __init__(self, plan_path: str, plan: DashboardPlan) -> None:
        self._plan_path = Path(plan_path).resolve()
        self._plan = plan
        self._cache: Dict[str, pd.DataFrame] = {}

    def load(self, dataset_id: str) -> pd.DataFrame:
        if dataset_id in self._cache:
            return self._cache[dataset_id]
        cfg = self._plan.dataset_by_id(dataset_id)
        path = Path(cfg.path)

        if not path.is_absolute():
            if path.exists():
                path = path.resolve()
            else:
                path = (self._plan_path.parent / path).resolve()

        if cfg.format == "csv":
            frame = pd.read_csv(path)
        else:
            raise ValueError(f"Unsupported dataset format: {cfg.format}")
        self._cache[dataset_id] = frame
        return frame
