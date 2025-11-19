"""Microsoft Agent Framework tools for chart generation adapters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Dict, Mapping

from adapters import get_registered_adapters, resolve_adapter
from adapters.base import AdapterResult, BaseAdapter
from app.autoviz_batch import SUPPORTED_SUFFIXES, render_autoviz_dashboard_for_file

try:  # pragma: no cover - fallback for local testing without Agent Framework
    from agent_framework import ai_function
except ImportError:  # pragma: no cover
    def ai_function(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(func: Any) -> Any:
            return func

        return decorator

try:
    from pydantic import Field
except ImportError:  # pragma: no cover
    Field = None  # type: ignore


def _field(description: str) -> Any:
    if Field is None:
        return description
    return Field(description=description)


@ai_function(name="list_chart_adapters", description="List adapters registered in this workspace.")
def list_chart_adapters() -> Dict[str, Any]:
    """Return adapter metadata so an orchestrator can decide which tool to call."""
    adapters: Dict[str, type[BaseAdapter]] = get_registered_adapters()
    entries = [
        {
            "name": name,
            "module": f"{cls.__module__}.{cls.__qualname__}",
        }
        for name, cls in sorted(adapters.items())
    ]
    return {"adapters": entries}


@ai_function(
    name="render_dashboard_section",
    description=(
        "Render a DashboardPlan section with a registered adapter and return the artifact path."
    ),
)
def render_dashboard_section(
    plan_json: Annotated[str, _field("DashboardPlan JSON payload to render.")],
    adapter_name: Annotated[
        str,
        _field("Adapter name (plotly_express, autoviz, deepchecks)."),
    ],
    output_dir: Annotated[
        str,
        _field("Directory where the HTML artifact should be written."),
    ] = "artifacts",
    section_id: Annotated[
        str | None,
        _field("Optional section id. Defaults to the first section if omitted."),
    ] = None,
    artifact_basename: Annotated[
        str | None,
        _field("Optional file stem to use for the output artifact."),
    ] = None,
) -> Dict[str, Any]:
    """Render a plan section via the requested adapter."""
    plan = _load_plan(plan_json)
    section = _select_section(plan, section_id)
    output_path = _build_output_path(section, adapter_name, output_dir, artifact_basename)

    adapter_cls = resolve_adapter(adapter_name)
    adapter = adapter_cls(section, output_path=output_path)
    result = adapter.render()
    return _result_to_dict(result)


@ai_function(
    name="render_autoviz_dashboard_from_file",
    description=(
        "Run AutoViz on a structured data file (csv/tsv/json/jsonl/xml) and return the artifact."
    ),
)
def render_autoviz_dashboard_from_file(
    dataset_path: Annotated[
        str,
        _field("Path to a dataset file with tabular data (csv, tsv, json, jsonl, xml)."),
    ],
    output_dir: Annotated[
        str,
        _field("Directory for generated HTML artifacts."),
    ] = "artifacts",
    max_rows: Annotated[
        int,
        _field("Maximum number of rows to analyze per dataset."),
    ] = 5000,
) -> Dict[str, Any]:
    """Convenience tool for batch scenarios without needing a DashboardPlan payload."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset '{dataset_path}' does not exist.")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(
            "Unsupported dataset format."
            f" Supported suffixes: {', '.join(sorted(SUPPORTED_SUFFIXES))}."
        )

    artifacts_dir = Path(output_dir)
    result = render_autoviz_dashboard_for_file(path, artifacts_dir=artifacts_dir, max_rows=max_rows)
    return _result_to_dict(result)


def _load_plan(plan_json: str) -> Mapping[str, Any]:
    data = json.loads(plan_json)
    if not isinstance(data, dict):
        raise ValueError("plan_json must decode to an object with a 'sections' array.")
    return data


def _select_section(plan: Mapping[str, Any], section_id: str | None) -> Mapping[str, Any]:
    sections = plan.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("DashboardPlan payload must include at least one section.")

    if section_id is None:
        return sections[0]

    for section in sections:
        if section.get("id") == section_id:
            return section
    raise KeyError(f"Section '{section_id}' not found in plan.")


def _build_output_path(
    section: Mapping[str, Any],
    adapter_name: str,
    output_dir: str,
    artifact_basename: str | None,
) -> Path:
    base = artifact_basename or section.get("id") or section.get("title") or "section"
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(base))
    slug = slug.strip("_") or "section"
    suffix = ".html"
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    return output / f"{slug}_{adapter_name.lower()}{suffix}"


def _result_to_dict(result: AdapterResult) -> Dict[str, Any]:
    return {
        "artifact_path": str(result.artifact_path),
        "metadata": result.metadata,
    }


__all__ = [
    "list_chart_adapters",
    "render_autoviz_dashboard_from_file",
    "render_dashboard_section",
]
