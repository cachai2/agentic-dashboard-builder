"""Render DashboardPlan sections via AutoViz."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .base import AdapterResult, BaseAdapter
from .utils import dataset_to_dataframe


class AutoVizAdapter(BaseAdapter):
    name = "autoviz"

    def render(self) -> AdapterResult:
        section = self._validated_section(self.section)
        dataset = dataset_to_dataframe(section["dataset"])
        dep_var = section.get("encodings", {}).get("y", "")
        output_path = self._validated_output_path(self.output_path)

        av = self._autoviz_class()
        autoviz_result = av.AutoViz(
            filename="",
            sep=",",
            depVar=dep_var,
            dfte=dataset,
            header=0,
            verbose=0,
            lowess=False,
            chart_format="html",
            max_rows_analyzed=min(len(dataset), 5000),
            max_cols_analyzed=len(dataset.columns),
            save_plot_dir=None,
        )

        chart_html = self._extract_chart_html(autoviz_result)
        if not chart_html:
            raise RuntimeError("AutoViz did not return HTML output; ensure chart_format='html'.")

        output_path.write_text(chart_html, encoding="utf-8")
        metadata = {
            "adapter": self.name,
            "rows": len(dataset),
            "columns": list(dataset.columns),
            "depVar": dep_var or None,
        }
        return AdapterResult(output_path, metadata)

    @staticmethod
    def _autoviz_class():
        try:
            from autoviz.AutoViz_Class import AutoViz_Class
        except ImportError as exc:  # pragma: no cover - exercised in runtime only
            raise RuntimeError(
                "AutoViz dependency missing. Run 'pip install autoviz' to enable this adapter."
            ) from exc
        return AutoViz_Class()

    @staticmethod
    def _validated_section(section: Mapping[str, Any]) -> Mapping[str, Any]:
        if "dataset" not in section:
            raise ValueError("DashboardPlan section must include a 'dataset' block.")
        return section

    @staticmethod
    def _validated_output_path(path: Path) -> Path:
        suffix = path.suffix.lower()
        if suffix not in {".html", ".htm"}:
            raise ValueError("AutoViz adapter only supports HTML artifacts.")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _extract_chart_html(result: Any) -> str:
        """Handle version-dependent return shapes from AutoViz."""
        if isinstance(result, str):
            return result.strip()

        if isinstance(result, Mapping):
            candidate = result.get("chart_html") or result.get("html")
            return candidate.strip() if isinstance(candidate, str) else ""

        if isinstance(result, (list, tuple)):
            # AutoViz commonly returns (df, html) or (df, html, figs).
            for item in reversed(result):
                if isinstance(item, str) and item.strip():
                    return item.strip()
                if isinstance(item, Mapping):
                    candidate = item.get("chart_html") or item.get("html")
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()

        return ""
