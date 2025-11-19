"""Renderer base classes and helper types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class RenderArtifact:
    """Represents the output of a renderer."""

    html: str
    metadata: Dict[str, Any]


class Renderer(ABC):
    """Abstract base class for all chart renderers."""

    @abstractmethod
    def render(self, plan_section: Any, data: Optional[pd.DataFrame]) -> RenderArtifact:
        """Render a plan section with the provided dataset."""
        raise NotImplementedError
