"""Adapter that renders DashboardPlan sections via Plotly Express."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import plotly.express as px

from .base import AdapterResult, BaseAdapter
from .utils import dataset_to_dataframe

ChartBuilder = Callable[..., Any]


class PlotlyExpressAdapter(BaseAdapter):
    name = "plotly_express"

    _BUILDERS: dict[str, ChartBuilder] = {
        "bar": px.bar,
        "line": px.line,
        "scatter": px.scatter,
        "area": px.area,
    }

    def render(self) -> AdapterResult:
        section = self._validated_section(self.section)
        dataset = dataset_to_dataframe(section["dataset"])
        encodings = section.get("encodings", {})

        x_field = encodings.get("x") or dataset.columns[0]
        y_field = encodings.get("y") or (
            dataset.columns[1] if len(dataset.columns) > 1 else dataset.columns[0]
        )
        color_field = encodings.get("color")

        chart_type = section.get("chartType", "bar").lower()
        builder = self._BUILDERS.get(chart_type)
        if builder is None:
            valid = ", ".join(sorted(self._BUILDERS))
            raise ValueError(
                f"Unsupported chartType '{chart_type}'. Available Plotly Express charts: {valid}"
            )

        figure = builder(
            dataset,
            x=x_field,
            y=y_field,
            color=color_field,
            title=section.get("title"),
            labels=section.get("labels"),
        )

        artifact = self._write_output(figure, self.output_path)
        metadata = {
            "adapter": self.name,
            "chartType": chart_type,
            "records": len(dataset),
            "columns": list(dataset.columns),
        }
        return AdapterResult(artifact, metadata)

    @staticmethod
    def _validated_section(section: Mapping[str, Any]) -> Mapping[str, Any]:
        if "dataset" not in section:
            raise ValueError("DashboardPlan section must include a 'dataset' block.")
        return section

    @staticmethod
    def _write_output(figure: Any, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = output_path.suffix.lower()
        if suffix in {".html", ".htm"}:
            figure.write_html(output_path, include_plotlyjs="cdn")
        elif suffix in {".png", ".jpg", ".jpeg"}:
            figure.write_image(output_path)
        else:
            raise ValueError(
                f"File extension '{suffix}' not supported. Use .html/.htm/.png/.jpg/.jpeg."
            )
        return output_path
