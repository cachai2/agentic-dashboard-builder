"""Common abstractions for chart adapters."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping


@dataclass(slots=True)
class AdapterResult:
    """Represents the output artifact produced by an adapter."""

    artifact_path: Path
    metadata: Dict[str, Any]


class BaseAdapter:
    """Contract for translating a DashboardPlan section into rendered output."""

    name: str = "base"

    def __init__(self, section: Mapping[str, Any], *, output_path: Path) -> None:
        self.section = section
        self.output_path = output_path

    def render(self) -> AdapterResult:
        """Render the plan section and return artifact metadata."""
        raise NotImplementedError
