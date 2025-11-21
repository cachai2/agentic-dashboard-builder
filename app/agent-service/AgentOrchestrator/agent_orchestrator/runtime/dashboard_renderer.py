from __future__ import annotations

import csv
import logging
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SectionBinding:
    chart_id: str
    title: str
    description: str
    operation: str | None


@dataclass(slots=True)
class RenderedSection:
    chart_id: str
    title: str
    description: str
    operation: str | None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RenderedDashboard:
    html: str
    source: str
    sections: List[RenderedSection] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CompiledPlan:
    payload: Dict[str, Any]
    bindings: List[SectionBinding]
    skipped: List[str]


class PlanConversionError(ValueError):
    """Raised when a planner chart cannot be converted to the renderer schema."""


class DashboardRenderer:
    """Dispatches between the Plotly rendering agent and the prebuilt adapters."""

    def __init__(self) -> None:
        self._chart_renderer = _ChartRenderingAdapter()
        self._autoviz_renderer = _AutoVizFallbackAdapter()

    def render(self, dataset_path: Path, plan_payload: Dict[str, Any] | None) -> RenderedDashboard | None:
        dataset_file = Path(dataset_path)
        if not dataset_file.exists():
            logger.warning("Dataset %s does not exist; dashboard rendering skipped", dataset_file)
            return None

        payload = plan_payload or {}
        if self._chart_renderer.available and payload:
            chart_result = self._chart_renderer.try_render(dataset_file, payload)
            if chart_result:
                return chart_result

        if self._autoviz_renderer.available:
            return self._autoviz_renderer.try_render(dataset_file)

        logger.info("No dashboard renderer available; falling back to basic HTML preview")
        return None


class _ChartRenderingAdapter:
    def __init__(self) -> None:
        self._composer = None
        self._plan_model = None
        self._available = False
        self._dataset_id = "uploaded_dataset"
        _bootstrap_chart_rendering_packages()
        self._bootstrap()

    @property
    def available(self) -> bool:
        return self._available and self._composer is not None and self._plan_model is not None

    def try_render(self, dataset_path: Path, plan_payload: Dict[str, Any]) -> RenderedDashboard | None:
        if not self.available:
            return None

        builder = _ChartRenderingPlanBuilder(dataset_path, dataset_id=self._dataset_id)
        try:
            compiled = builder.build(plan_payload)
            if compiled is None:
                if builder.skipped:
                    logger.info("ChartRendering skipped charts: %s", "; ".join(builder.skipped))
                return None

            assert self._plan_model is not None  # for mypy
            dashboard_plan = self._plan_model.model_validate(compiled.payload)
            try:
                artifact = self._composer.render_plan(str(dataset_path), dashboard_plan)  # type: ignore[call-arg]
            except Exception:
                logger.exception("ChartRendering agent failed to render plan")
                return None
        finally:
            builder.cleanup()

        sections_metadata = artifact.metadata.get("sections", []) if isinstance(artifact.metadata, Mapping) else []
        rendered_sections: List[RenderedSection] = []
        for idx, binding in enumerate(compiled.bindings):
            metadata = sections_metadata[idx] if idx < len(sections_metadata) else {}
            rendered_sections.append(
                RenderedSection(
                    chart_id=binding.chart_id,
                    title=binding.title,
                    description=binding.description,
                    operation=binding.operation,
                    metadata=dict(metadata),
                )
            )

        return RenderedDashboard(
            html=artifact.html,
            source="chart-rendering",
            sections=rendered_sections,
            skipped=compiled.skipped,
            metadata=artifact.metadata,
        )

    def _bootstrap(self) -> None:
        module_roots = ["ChartRenderingAgent", "Playground.ChartRenderingAgent"]
        for root in module_roots:
            try:
                composer_module = import_module(f"{root}.app.composer")
                models_module = import_module(f"{root}.app.models")
                toolkit_module = import_module(f"{root}.app.toolkit")
            except ModuleNotFoundError:
                continue

            PlanComposer = getattr(composer_module, "PlanComposer", None)
            DashboardPlan = getattr(models_module, "DashboardPlan", None)
            build_renderer_registry = getattr(toolkit_module, "build_renderer_registry", None)
            if not (PlanComposer and DashboardPlan and build_renderer_registry):
                continue

            self._plan_model = DashboardPlan
            self._composer = PlanComposer(build_renderer_registry())
            self._available = True
            logger.info("Initialized ChartRendering adapter from %s", root)
            return

        logger.warning("ChartRenderingAgent package not available; Plotly renderer disabled")


def _detect_repo_root() -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "azure.yaml").exists():
            return parent
    return None


def _bootstrap_chart_rendering_packages() -> None:
    repo_root = _detect_repo_root()
    candidates: List[Path] = []
    if repo_root:
        candidates.extend(
            [
                repo_root / "app" / "agent-service" / "ChartRenderingAgent",
                repo_root / "ChartRenderingAgent",
                repo_root / "Playground" / "ChartRenderingAgent",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            path_str = str(candidate)
            if path_str not in sys.path:
                sys.path.insert(0, path_str)



class _ChartRenderingPlanBuilder:
    def __init__(self, dataset_path: Path, *, dataset_id: str) -> None:
        dataset_file = Path(dataset_path).resolve()
        self._dataset_id = dataset_id
        self._source_dataset = dataset_file
        self._dataset_entry = {"id": dataset_id, "path": str(dataset_file), "format": "csv"}
        self._datasets: List[Dict[str, Any]] = [self._dataset_entry]
        self._registered_dataset_ids: set[str] = {dataset_id}
        self._sections: List[Dict[str, Any]] = []
        self._bindings: List[SectionBinding] = []
        self._skipped: List[str] = []
        self._chart_counter = 0
        self._inline_artifacts: List[Path] = []

    @property
    def skipped(self) -> List[str]:
        return list(self._skipped)

    def build(self, payload: Dict[str, Any]) -> CompiledPlan | None:
        plan_dict = self._extract_plan(payload)
        sections = plan_dict.get("sections")
        if not isinstance(sections, list):
            return None

        for section in sections:
            charts = section.get("charts") or []
            if not isinstance(charts, list):
                continue
            for chart in charts:
                if not isinstance(chart, MutableMapping):
                    continue
                self._chart_counter += 1
                try:
                    plan_section, binding = self._convert_chart(section, chart)
                except PlanConversionError as exc:
                    chart_id = str(chart.get("id") or f"chart-{self._chart_counter}")
                    self._skipped.append(f"{chart_id}: {exc}")
                    continue
                self._sections.append(plan_section)
                self._bindings.append(binding)

        if not self._sections:
            return None

        payload = {"datasets": self._datasets, "sections": self._sections}
        return CompiledPlan(payload=payload, bindings=list(self._bindings), skipped=self.skipped)

    def _extract_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        plan = payload.get("plan")
        return plan if isinstance(plan, dict) else payload

    def _convert_chart(self, section: Mapping[str, Any], chart: MutableMapping[str, Any]) -> tuple[Dict[str, Any], SectionBinding]:
        query = chart.get("query")
        if not isinstance(query, Mapping):
            raise PlanConversionError("chart missing query block")

        operation = query.get("operation")
        if not isinstance(operation, str):
            raise PlanConversionError("chart query missing operation")

        builder = self._builder_for_operation(operation)
        plan_section = builder(section, chart, query)
        binding = self._build_binding(section, chart, operation)
        return plan_section, binding

    def _builder_for_operation(self, operation: str):
        mapping = {
            "timeseries_agg": self._build_timeseries_section,
            "groupby_agg": self._build_groupby_section,
            "topk": self._build_groupby_section,
            "distribution": self._build_distribution_section,
            "outliers": self._build_outliers_section,
            "kpi": self._build_kpi_section,
            "scatter": self._build_scatter_section,
            "funnel": self._build_funnel_section,
        }
        builder = mapping.get(operation)
        if not builder:
            raise PlanConversionError(f"operation '{operation}' not supported")
        return builder

    def _build_binding(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        operation: str | None,
    ) -> SectionBinding:
        title = str(chart.get("title") or section.get("title") or "Chart")
        description = str(chart.get("insight") or section.get("description") or "")
        chart_id = str(chart.get("id") or f"chart-{self._chart_counter}")
        return SectionBinding(chart_id=chart_id, title=title, description=description, operation=operation)

    def _build_timeseries_section(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> Dict[str, Any]:
        x_col = query.get("x")
        y_col = query.get("y")
        if not (isinstance(x_col, str) and isinstance(y_col, str)):
            raise PlanConversionError("timeseries charts require 'x' and 'y' fields")

        return {
            "operation": "timeseries",
            "title": chart.get("title") or section.get("title") or "Timeseries",
            "dataset": self._dataset_id,
            "x": {"column": x_col, "grain": query.get("time_grain")},
            "series": [
                {
                    "id": y_col,
                    "column": y_col,
                    "label": chart.get("title") or self._prettify(y_col),
                }
            ],
        }

    def _build_groupby_section(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> Dict[str, Any]:
        dimension = query.get("x") or query.get("dimension")
        metric = query.get("y") or query.get("metric")
        if not (isinstance(dimension, str) and isinstance(metric, str)):
            raise PlanConversionError("groupby charts require categorical 'x' and numeric 'y'")

        limit = self._coerce_positive_int(query.get("top_k"))
        agg = self._normalize_agg(query.get("agg"))
        return {
            "operation": "groupby",
            "title": chart.get("title") or section.get("title") or "Comparison",
            "dataset": self._dataset_id,
            "dimension": dimension,
            "metric": metric,
            "aggregation": agg,
            "options": {"limit": limit},
        }

    def _build_distribution_section(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> Dict[str, Any]:
        metric = query.get("y") or query.get("metric")
        if not isinstance(metric, str):
            raise PlanConversionError("distribution charts require a numeric 'y' field")

        return {
            "operation": "distribution",
            "title": chart.get("title") or section.get("title") or "Distribution",
            "dataset": self._dataset_id,
            "metric": metric,
        }

    def _build_outliers_section(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> Dict[str, Any]:
        x_col = query.get("x")
        y_col = query.get("y")
        if not (isinstance(x_col, str) and isinstance(y_col, str)):
            raise PlanConversionError("outlier charts require both 'x' and 'y'")

        return {
            "operation": "outliers",
            "title": chart.get("title") or section.get("title") or "Anomalies",
            "dataset": self._dataset_id,
            "x": {"column": x_col, "grain": query.get("time_grain")},
            "y": y_col,
        }

    def _build_kpi_section(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> Dict[str, Any]:
        cards_input = chart.get("cards") or query.get("cards")
        if not isinstance(cards_input, list):
            raise PlanConversionError("kpi charts require a list of cards")

        cards: List[Dict[str, Any]] = []
        for item in cards_input:
            if not isinstance(item, Mapping):
                continue
            title = str(item.get("title") or chart.get("title") or "KPI")
            value = item.get("value")
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            card_payload = {
                "title": title,
                "value": numeric_value,
            }
            if item.get("unit"):
                card_payload["unit"] = item["unit"]
            if item.get("delta") is not None:
                card_payload["delta"] = item.get("delta")
            if item.get("trend"):
                card_payload["trend"] = item.get("trend")
            if item.get("trend_label"):
                card_payload["trend_label"] = item.get("trend_label")
            cards.append(card_payload)

        if not cards:
            raise PlanConversionError("kpi cards missing numeric values")

        layout = chart.get("layout") or query.get("layout") or "grid"
        return {
            "operation": "kpi",
            "title": chart.get("title") or section.get("title") or "Customer Snapshot",
            "layout": layout,
            "cards": cards,
        }

    def _build_scatter_section(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> Dict[str, Any]:
        x_col = query.get("x")
        y_col = query.get("y")
        if not (isinstance(x_col, str) and isinstance(y_col, str)):
            raise PlanConversionError("scatter charts require 'x' and 'y' columns")

        dataset_id = query.get("dataset") or self._dataset_id
        self._ensure_dataset_registered(dataset_id)
        options = query.get("options") if isinstance(query.get("options"), Mapping) else {}
        tooltip_fields = query.get("tooltip_fields")
        if isinstance(tooltip_fields, list):
            tooltip_fields = [str(field) for field in tooltip_fields if isinstance(field, str)]
        else:
            tooltip_fields = None

        opacity_value = options.get("opacity", 0.85)
        try:
            opacity_value = float(opacity_value)
        except (TypeError, ValueError):
            opacity_value = 0.85

        return {
            "operation": "scatter",
            "title": chart.get("title") or section.get("title") or "Scatter",
            "dataset": dataset_id,
            "x": x_col,
            "y": y_col,
            "size": query.get("size") if isinstance(query.get("size"), str) else None,
            "color": query.get("color") if isinstance(query.get("color"), str) else None,
            "text": query.get("text") if isinstance(query.get("text"), str) else None,
            "tooltip_fields": tooltip_fields,
            "options": {
                "trendline": bool(options.get("trendline", query.get("trendline", True))),
                "opacity": opacity_value,
            },
        }

    def _build_funnel_section(
        self,
        section: Mapping[str, Any],
        chart: Mapping[str, Any],
        query: Mapping[str, Any],
    ) -> Dict[str, Any]:
        stage_column = self._coerce_string(query.get("stage_column"), "stage")
        value_column = self._coerce_string(query.get("value_column"), "count")
        comparison_column = self._coerce_string(query.get("comparison_column"), "prev_count", optional=True)
        data_rows = query.get("data")
        if not isinstance(data_rows, list) or not data_rows:
            raise PlanConversionError("funnel charts require inline 'data' rows")

        dataset_hint = query.get("dataset") or query.get("dataset_hint") or f"{self._dataset_id}_funnel_{self._chart_counter}"
        dataset_id, dataset_path = self._write_inline_dataset(dataset_hint, data_rows)
        stages = query.get("stages") if isinstance(query.get("stages"), list) else None
        if not stages:
            stages = [row.get(stage_column, f"Stage {idx+1}") for idx, row in enumerate(data_rows)]

        options = query.get("options") if isinstance(query.get("options"), Mapping) else {}
        section_payload = {
            "operation": "funnel",
            "title": chart.get("title") or section.get("title") or "Retention Funnel",
            "dataset": dataset_id,
            "stage_column": stage_column,
            "value_column": value_column,
            "stages": stages,
            "options": {
                "show_conversion": bool(options.get("show_conversion", True)),
                "show_delta": bool(options.get("show_delta", True)),
            },
        }
        if comparison_column:
            section_payload["comparison_column"] = comparison_column

        self._datasets.append({"id": dataset_id, "path": str(dataset_path), "format": "csv"})
        return section_payload

    def _write_inline_dataset(self, dataset_hint: str, rows: List[Mapping[str, Any]]) -> tuple[str, Path]:
        dataset_id = self._sanitize_id(dataset_hint) if dataset_hint else f"inline_{uuid.uuid4().hex[:8]}"
        filename = f"{self._source_dataset.stem}__{dataset_id}.csv"
        target_path = self._source_dataset.parent / filename
        fieldnames: List[str] = []
        observed = set()
        for row in rows:
            if isinstance(row, Mapping):
                for key in row.keys():
                    if key not in observed:
                        observed.add(key)
                        fieldnames.append(str(key))
        if not fieldnames:
            raise PlanConversionError("inline dataset rows missing columns")

        with target_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                writer.writerow({key: row.get(key) for key in fieldnames})

        self._inline_artifacts.append(target_path)
        return dataset_id, target_path

    def _ensure_dataset_registered(self, dataset_id: str) -> None:
        if dataset_id in self._registered_dataset_ids:
            return
        self._datasets.append({"id": dataset_id, "path": str(self._source_dataset), "format": "csv"})
        self._registered_dataset_ids.add(dataset_id)

    def _coerce_string(self, value: Any, fallback: str, *, optional: bool = False) -> Optional[str]:
        if value is None:
            return None if optional else fallback
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        return None if optional else fallback

    @staticmethod
    def _sanitize_id(value: str) -> str:
        sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
        sanitized = sanitized.strip("_")
        return sanitized or f"inline_{uuid.uuid4().hex[:6]}"

    def cleanup(self) -> None:
        for artifact_path in self._inline_artifacts:
            try:
                artifact_path.unlink(missing_ok=True)
            except OSError:
                logger.debug("Failed to remove inline dataset %s", artifact_path, exc_info=True)

    def _normalize_agg(self, value: Any) -> str:
        if not isinstance(value, str):
            return "sum"
        normalized = value.lower()
        if normalized in {"sum", "avg", "mean", "count"}:
            return normalized
        if normalized in {"average"}:
            return "avg"
        if normalized in {"min", "max", "median"}:
            return "avg"
        return "sum"

    def _coerce_positive_int(self, value: Any, default: int = 6) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _prettify(column: str) -> str:
        column = column.replace("_", " ")
        return column.title()


class _AutoVizFallbackAdapter:
    def __init__(self) -> None:
        self._render_fn = None
        self._available = False
        self._bootstrap()

    @property
    def available(self) -> bool:
        return self._available and self._render_fn is not None

    def try_render(self, dataset_path: Path) -> RenderedDashboard | None:
        if not self.available:
            return None

        try:
            with tempfile.TemporaryDirectory(prefix="autoviz-") as tmp_dir:
                result = self._render_fn(dataset_path=dataset_path, artifacts_dir=Path(tmp_dir))
                artifact_path = Path(result.artifact_path)
                if not artifact_path.exists():
                    logger.warning("AutoViz artifact %s missing", artifact_path)
                    return None
                html = artifact_path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("AutoViz fallback renderer failed")
            return None

        metadata = getattr(result, "metadata", {}) or {}
        section = RenderedSection(
            chart_id="autoviz-dashboard",
            title=f"AutoViz Overview ({dataset_path.name})",
            description="Exploratory AutoViz dashboard",
            operation="autoviz",
            metadata=metadata,
        )
        return RenderedDashboard(html=html, source="autoviz", sections=[section], metadata=metadata)

    def _bootstrap(self) -> None:
        module_roots = ["Playground.PrebuiltChartGenAgent.app.autoviz_batch"]
        for module_name in module_roots:
            try:
                module = import_module(module_name)
            except ModuleNotFoundError:
                continue
            render_fn = getattr(module, "render_autoviz_dashboard_for_file", None)
            if render_fn:
                self._render_fn = render_fn
                self._available = True
                logger.info("Initialized AutoViz fallback renderer from %s", module_name)
                return
        logger.info("AutoViz adapter not available; install optional dependencies to enable dashboard fallbacks")


__all__ = [
    "DashboardRenderer",
    "RenderedDashboard",
    "RenderedSection",
]
