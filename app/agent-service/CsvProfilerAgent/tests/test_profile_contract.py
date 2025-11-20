"""Contract tests for the dataset profile schema."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from app.profiling import ProfilingOptions, profile_csv_path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "dataset_profile.schema.json"
SAMPLE_CSV = ROOT / "samples" / "retail_superstore_sample.csv"


def test_sample_profile_matches_contract() -> None:
    profile = profile_csv_path(SAMPLE_CSV)
    schema = json.loads(SCHEMA_PATH.read_text())
    validate(instance=profile.model_dump(mode="json"), schema=schema)
    assert profile.row_count == 10_000
    assert profile.sampled_row_count == profile.row_count
    assert profile.sampling_ratio == 1.0
    assert profile.column_count >= 10
    assert profile.columns, "Columns should not be empty"


def test_numeric_and_categorical_stats_present() -> None:
    profile = profile_csv_path(SAMPLE_CSV)
    numeric_columns = [c for c in profile.columns if c.semantic_type == "numeric"]
    categorical_columns = [c for c in profile.columns if c.semantic_type == "categorical"]

    assert numeric_columns, "Expected at least one numeric column"
    assert categorical_columns, "Expected at least one categorical column"

    for column in numeric_columns:
        assert column.numeric_stats is not None
        assert column.numeric_stats.min is None or column.numeric_stats.max is None or column.numeric_stats.max >= column.numeric_stats.min

    for column in categorical_columns:
        assert column.categorical_stats is not None
        assert column.categorical_stats.top_values, "Categorical columns should expose top values"


def test_sampling_metadata_changes_when_max_rows_set() -> None:
    profile = profile_csv_path(
        SAMPLE_CSV,
        options=ProfilingOptions(max_rows=500),
    )
    assert profile.row_count == 10_000
    assert profile.sampled_row_count == 500
    assert profile.sampling_ratio == 0.05


def test_annotations_block_present() -> None:
    profile = profile_csv_path(SAMPLE_CSV)
    annotations = profile.llm_annotations
    assert annotations is not None
    assert annotations.get("kpis")
