"""Shared abstractions for dataset preprocessing pipelines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd


@dataclass(slots=True)
class DatasetPreprocessor(ABC):
    """Base contract all dataset preprocessors must satisfy."""

    name: str
    description: str
    default_input: Path
    default_output: Path

    @abstractmethod
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a cleaned/enriched copy of *df*."""

    def run(self, input_path: Path | None = None, output_path: Path | None = None) -> Path:
        input_path = input_path or self.default_input
        output_path = output_path or self.default_output
        frame = pd.read_csv(input_path)
        cleaned = self.process(frame)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(output_path, index=False)
        return output_path


class _PreprocessorRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, DatasetPreprocessor] = {}

    def register(self, preprocessor: DatasetPreprocessor) -> None:
        if preprocessor.name in self._registry:
            raise ValueError(f"Duplicate preprocessor name registered: {preprocessor.name}")
        self._registry[preprocessor.name] = preprocessor

    def get(self, name: str) -> DatasetPreprocessor:
        try:
            return self._registry[name]
        except KeyError as exc:  # pragma: no cover - simple guard
            known = ", ".join(sorted(self._registry)) or "<none>"
            raise KeyError(f"Unknown dataset '{name}'. Available: {known}") from exc

    def list(self) -> List[DatasetPreprocessor]:
        return list(self._registry.values())


registry = _PreprocessorRegistry()


def register_preprocessor(preprocessor: DatasetPreprocessor) -> None:
    registry.register(preprocessor)


def get_preprocessor(name: str) -> DatasetPreprocessor:
    return registry.get(name)


def list_preprocessors() -> List[DatasetPreprocessor]:
    return registry.list()
