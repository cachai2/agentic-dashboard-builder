"""Render DashboardPlan sections via AutoViz."""
from __future__ import annotations

from html import escape
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping

from .base import AdapterResult, BaseAdapter
from .utils import dataset_to_dataframe


class AutoVizAdapter(BaseAdapter):
    name = "autoviz"

    def render(self) -> AdapterResult:
        section = self._validated_section(self.section)
        dataset = dataset_to_dataframe(section["dataset"])
        dep_var = section.get("encodings", {}).get("y", "")
        output_path = self._validated_output_path(self.output_path)

        temp_dir = output_path.parent / f"{output_path.stem}_autoviz"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        av = self._autoviz_class()

        def _run_autoviz(current_dep: str) -> None:
            av.AutoViz(
                filename="",
                sep=",",
                depVar=current_dep,
                dfte=dataset,
                header=0,
                verbose=0,
                lowess=False,
                chart_format="html",
                max_rows_analyzed=min(len(dataset), 5000),
                max_cols_analyzed=len(dataset.columns),
                save_plot_dir=str(temp_dir),
            )

        try:
            _run_autoviz(dep_var)
        except ValueError as exc:
            if dep_var:
                # Some AutoViz builds error when saving charts with certain dep vars; retry without.
                shutil.rmtree(temp_dir, ignore_errors=True)
                temp_dir.mkdir(parents=True, exist_ok=True)
                dep_var = ""
                _run_autoviz(dep_var)
            else:
                raise exc

        chart_html = self._combine_autoviz_html(section.get("title", output_path.stem), temp_dir.rglob("*.html"))
        if not chart_html:
            raise RuntimeError("AutoViz did not emit any HTML files; ensure chart_format='html'.")

        output_path.write_text(chart_html, encoding="utf-8")
        shutil.rmtree(temp_dir, ignore_errors=True)
        metadata = {
            "adapter": self.name,
            "rows": len(dataset),
            "columns": list(dataset.columns),
            "depVar": dep_var or None,
            "charts": chart_html.count("<iframe"),
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
    def _combine_autoviz_html(title: str | None, html_files: Iterable[Path]) -> str:
        files = sorted(html_files)
        if not files:
            return ""

        sections: list[str] = []
        for idx, file_path in enumerate(files, start=1):
            raw_html = file_path.read_text(encoding="utf-8")
            section_title = f"Chart {idx}: {file_path.stem.replace('_', ' ').title()}"
            sections.append(
                "\n".join(
                    [
                        f"<section>",
                        f"  <h2>{escape(section_title)}</h2>",
                        "  <iframe",
                        "    loading=\"lazy\"",
                        "    style=\"width:100%;height:600px;border:1px solid #ddd;margin-bottom:1rem;\"",
                        f"    srcdoc=\"{escape(raw_html, quote=True)}\"></iframe>",
                        "</section>",
                    ]
                )
            )

        heading = escape(title) if title else "AutoViz Dashboard"
        body = "\n".join(sections)
        return (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            "  <meta charset='utf-8'/>\n"
            f"  <title>{heading}</title>\n"
            "  <style>body{font-family:Arial,Helvetica,sans-serif;margin:0;padding:1rem;background:#f9fafb;}"
            "h1{font-size:1.5rem;margin-top:0;}h2{font-size:1.1rem;margin:1.5rem 0 0.5rem;}"
            "section{background:#fff;padding:1rem;border-radius:0.5rem;box-shadow:0 1px 3px rgba(0,0,0,0.1);"
            "margin-bottom:1rem;}iframe{background:#fff;}" "</style>\n"
            "</head>\n"
            "<body>\n"
            f"  <h1>{heading}</h1>\n"
            f"  {body}\n"
            "</body>\n"
            "</html>"
        )
