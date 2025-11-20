"""Renderer registry allows dynamic lookup by operation name."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import pandas as pd

from renderers.base import RenderArtifact, Renderer

RendererFactory = Callable[[Any, Optional[pd.DataFrame]], RenderArtifact]


class RendererRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Renderer] = {}

    def register(self, operation: str, renderer: Renderer) -> None:
        self._registry[operation] = renderer

    def render(
        self, operation: str, plan_section: Any, data: Optional[pd.DataFrame]
    ) -> RenderArtifact:
        if operation not in self._registry:
            raise KeyError(f"Renderer for operation '{operation}' is not registered")
        renderer = self._registry[operation]
        return renderer.render(plan_section, data)
