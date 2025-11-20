"""Compose dashboard plans into an embeddable HTML document."""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from renderers.base import RenderArtifact

from .data_loader import DataCatalog
from .models import DashboardPlan
from .registry import RendererRegistry

HTML_SHELL = """<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <title>Chart Rendering Agent</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; margin: 24px; background: #fafafa; color: #111; }}
        section {{ margin-bottom: 40px; border: 1px solid #e0e0e0; border-radius: 12px; background: #fff; padding: 16px; }}
        h2 {{ margin-top: 0; font-size: 1.1rem; }}
    </style>
</head>
<body>
{sections}
</body>
</html>
"""


class PlanComposer:
    def __init__(self, registry: RendererRegistry) -> None:
        self._registry = registry

    def render_plan(self, plan_path: str, plan: DashboardPlan) -> RenderArtifact:
        catalog = DataCatalog(plan_path, plan)
        section_fragments: List[str] = []
        metadata_payload = {"sections": []}

        for section in plan.sections:
            dataset = self._resolve_dataset(section, catalog)
            rendered = self._render_section(section, dataset)
            metadata_payload["sections"].append(rendered.metadata)
            title = section.title or section.operation.title()
            section_fragments.append(
                f"<section><h2>{title}</h2>{rendered.html}</section>"
            )

        html = HTML_SHELL.format(sections="\n".join(section_fragments))
        return RenderArtifact(html=html, metadata=metadata_payload)

    def _render_section(self, section, dataset):
        return self._registry.render(section.operation, section, dataset)

    def _resolve_dataset(self, section, catalog: DataCatalog) -> Optional[pd.DataFrame]:
        dataset_id = getattr(section, "dataset", None)
        if dataset_id:
            return catalog.load(dataset_id)
        return None
