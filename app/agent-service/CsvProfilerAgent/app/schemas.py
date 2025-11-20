"""Pydantic models that mirror the Dataset Profile contract."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NumericStats(BaseModel):
    min: Optional[float]
    max: Optional[float]
    mean: Optional[float]
    stddev: Optional[float]
    p05: Optional[float]
    p95: Optional[float]


class TopValue(BaseModel):
    value: Optional[str]
    count: int = Field(ge=0)
    percent: float = Field(ge=0, le=100)


class CategoricalStats(BaseModel):
    top_values: List[TopValue]


class ColumnProfile(BaseModel):
    name: str
    semantic_type: str = Field(pattern="^(numeric|categorical|datetime|boolean)$")
    null_count: int = Field(ge=0)
    null_pct: float = Field(ge=0, le=100)
    distinct_count: int = Field(ge=0)
    example: Optional[str]
    numeric_stats: Optional[NumericStats] = None
    categorical_stats: Optional[CategoricalStats] = None


class DatasetProfile(BaseModel):
    dataset_name: str
    row_count: int = Field(ge=0)
    sampled_row_count: int = Field(ge=0)
    sampling_ratio: float = Field(ge=0, le=1)
    column_count: int = Field(ge=0)
    generated_at: datetime
    columns: List[ColumnProfile]
    llm_annotations: Optional[dict] = None
