"""Pydantic models describing the dashboard plan contract."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class AxisConfig(BaseModel):
    column: str
    grain: Optional[str] = None


class SeriesStyle(BaseModel):
    dash: Optional[str] = None
    color: Optional[str] = None
    width: Optional[int] = Field(default=2, ge=1)


class SeriesConfig(BaseModel):
    id: str
    column: str
    label: Optional[str] = None
    axis: Literal["primary", "secondary"] = "primary"
    style: Optional[SeriesStyle] = None


class ForecastConfig(BaseModel):
    lower: str
    upper: str
    label: Optional[str] = "Forecast"


class ComparisonConfig(BaseModel):
    mode: Literal["previous_period"]
    offset_days: int = Field(default=30, gt=0)


class EventMarker(BaseModel):
    ts: datetime
    label: str
    annotation: Optional[str] = None


class TimeseriesOptions(BaseModel):
    compact: bool = False
    y_axis_format: Optional[str] = None
    rolling_window: int = Field(default=1, ge=1)
    show_export: bool = True


class TimeseriesSection(BaseModel):
    operation: Literal["timeseries"]
    title: Optional[str] = None
    dataset: str
    x: AxisConfig
    series: List[SeriesConfig]
    forecast: Optional[ForecastConfig] = None
    comparison: Optional[ComparisonConfig] = None
    events: List[EventMarker] = Field(default_factory=list)
    options: TimeseriesOptions = Field(default_factory=TimeseriesOptions)


class GroupByOptions(BaseModel):
    orientation: Literal["vertical", "horizontal"] = "vertical"
    sort: Literal["asc", "desc", "none"] = "desc"
    limit: int = Field(default=6, ge=1)
    show_reference: bool = True
    reference_value: Optional[float] = None


class GroupBySection(BaseModel):
    operation: Literal["groupby"]
    title: Optional[str] = None
    dataset: str
    dimension: str
    metric: str
    aggregation: Literal["sum", "avg", "mean", "count"] = "sum"
    options: GroupByOptions = Field(default_factory=GroupByOptions)


class CompositionOptions(BaseModel):
    normalize: bool = False
    kind: Literal["stacked_area", "stacked_bar"] = "stacked_area"


class CompositionSection(BaseModel):
    operation: Literal["composition"]
    title: Optional[str] = None
    dataset: str
    x: Optional[AxisConfig] = None
    stacks: List[str]
    options: CompositionOptions = Field(default_factory=CompositionOptions)


class DistributionOptions(BaseModel):
    bins: int = Field(default=30, ge=1)
    overlay: Literal["density", "none"] = "density"
    show_boxplot: bool = False


class DistributionSection(BaseModel):
    operation: Literal["distribution"]
    title: Optional[str] = None
    dataset: str
    metric: str
    comparison_metric: Optional[str] = None
    options: DistributionOptions = Field(default_factory=DistributionOptions)


class ThresholdConfig(BaseModel):
    value: float
    direction: Literal["above", "below"] = "above"


class AnomalySection(BaseModel):
    operation: Literal["outliers"]
    title: Optional[str] = None
    dataset: str
    x: AxisConfig
    y: str
    threshold: Optional[ThresholdConfig] = None
    flag_column: Optional[str] = None
    events: List[EventMarker] = Field(default_factory=list)


class KpiDelta(BaseModel):
    value: float
    direction: Literal["up", "down", "flat"] = "up"
    label: Optional[str] = None


class KpiCard(BaseModel):
    title: str
    value: float
    unit: Optional[str] = None
    delta: Optional[KpiDelta] = None
    trend: List[float] = Field(default_factory=list)
    trend_label: Optional[str] = None


class KPISection(BaseModel):
    operation: Literal["kpi"]
    title: Optional[str] = None
    cards: List[KpiCard]
    layout: Literal["grid", "row"] = "grid"


class ScatterQuadrantConfig(BaseModel):
    x: float
    y: float
    labels: Optional[List[str]] = None


class ScatterOptions(BaseModel):
    trendline: bool = True
    opacity: float = Field(default=0.85, ge=0.1, le=1)


class ScatterSection(BaseModel):
    operation: Literal["scatter"]
    title: Optional[str] = None
    dataset: str
    x: str
    y: str
    size: Optional[str] = None
    color: Optional[str] = None
    text: Optional[str] = None
    tooltip_fields: List[str] = Field(default_factory=list)
    quadrant: Optional[ScatterQuadrantConfig] = None
    options: ScatterOptions = Field(default_factory=ScatterOptions)


class FunnelOptions(BaseModel):
    show_conversion: bool = True
    show_delta: bool = True


class FunnelSection(BaseModel):
    operation: Literal["funnel"]
    title: Optional[str] = None
    dataset: str
    stage_column: str
    value_column: str
    comparison_column: Optional[str] = None
    stages: List[str] = Field(default_factory=list)
    options: FunnelOptions = Field(default_factory=FunnelOptions)


SectionType = Annotated[
    Union[
        TimeseriesSection,
        GroupBySection,
        CompositionSection,
        DistributionSection,
        AnomalySection,
        KPISection,
        ScatterSection,
        FunnelSection,
    ],
    Field(discriminator="operation"),
]


class DatasetConfig(BaseModel):
    id: str
    path: str
    format: Literal["csv"] = "csv"


class DashboardPlan(BaseModel):
    datasets: List[DatasetConfig]
    sections: List[SectionType]
    metadata: Dict[str, str] | None = None

    def dataset_by_id(self, dataset_id: str) -> DatasetConfig:
        for dataset in self.datasets:
            if dataset.id == dataset_id:
                return dataset
        raise KeyError(f"Dataset '{dataset_id}' not found in plan")
