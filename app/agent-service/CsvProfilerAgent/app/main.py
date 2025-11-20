"""FastAPI surface for the CSV profiler."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from opentelemetry import trace
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .profiling import ProfilingOptions, profile_csv_bytes, profile_csv_path
from .schemas import DatasetProfile
from .tracing import configure_tracing, get_tracer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("csv_profiler")

app = FastAPI(title="CSV Profiler Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
configure_tracing(app)
TRACER = get_tracer()


class ProfilePathRequest(BaseModel):
    path: str = Field(..., description="Absolute or relative CSV path")
    dataset_name: Optional[str] = Field(None, description="Override dataset label")
    max_rows: Optional[int] = Field(
        None,
        description="Deterministic sample size if dataset exceeds this many rows",
        ge=1,
    )


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def _annotate_current_span(
    profile: DatasetProfile,
    duration_ms: float,
    max_rows: Optional[int],
) -> None:
    span = trace.get_current_span()
    if span is None or not span.is_recording():
        return
    span.set_attributes(
        {
            "csv_profiler.dataset_name": profile.dataset_name,
            "csv_profiler.row_count": profile.row_count,
            "csv_profiler.sampled_row_count": profile.sampled_row_count,
            "csv_profiler.sampling_ratio": profile.sampling_ratio,
            "csv_profiler.column_count": profile.column_count,
            "csv_profiler.duration_ms": round(duration_ms, 2),
            "csv_profiler.sample_applied": profile.sampled_row_count != profile.row_count,
            "csv_profiler.max_rows": max_rows if max_rows is not None else -1,
        }
    )


def _emit_profile_generated(
    profile: DatasetProfile,
    duration_ms: float,
    max_rows: Optional[int],
) -> None:
    _annotate_current_span(profile, duration_ms, max_rows)
    sample_applied = profile.sampled_row_count != profile.row_count
    logger.info(
        "profile_generated",
        extra={
            "event": "profile_generated",
            "dataset_name": profile.dataset_name,
            "row_count": profile.row_count,
            "sampled_row_count": profile.sampled_row_count,
            "sampling_ratio": profile.sampling_ratio,
            "sample_applied": sample_applied,
            "max_rows": max_rows,
            "column_count": profile.column_count,
            "duration_ms": round(duration_ms, 2),
        },
    )


def _options(max_rows: Optional[int]) -> ProfilingOptions:
    return ProfilingOptions(max_rows=max_rows)


@app.post("/profile/path", response_model=DatasetProfile)
def profile_by_path(payload: ProfilePathRequest) -> DatasetProfile:
    start = perf_counter()
    with TRACER.start_as_current_span("profile.path") as span:
        span.set_attributes(
            {
                "csv_profiler.input_type": "filesystem",
                "csv_profiler.max_rows": payload.max_rows if payload.max_rows else -1,
            }
        )
        try:
            profile = profile_csv_path(
                payload.path,
                payload.dataset_name,
                options=_options(payload.max_rows),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    duration_ms = (perf_counter() - start) * 1000
    _emit_profile_generated(profile, duration_ms, payload.max_rows)
    return profile


@app.post("/profile/upload", response_model=DatasetProfile)
async def profile_upload(
    file: UploadFile = File(...),
    dataset_name: Optional[str] = Form(None),
    max_rows: Optional[int] = Form(
        None,
        description="Deterministic sample size if dataset exceeds this many rows",
    ),
) -> DatasetProfile:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file was empty")
    dataset_label = dataset_name or file.filename or "uploaded"
    start = perf_counter()
    with TRACER.start_as_current_span("profile.upload") as span:
        span.set_attributes(
            {
                "csv_profiler.input_type": "upload",
                "csv_profiler.max_rows": max_rows if max_rows else -1,
                "csv_profiler.filename": file.filename or "unknown",
            }
        )
        try:
            profile = profile_csv_bytes(
                content,
                dataset_label,
                options=_options(max_rows),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    duration_ms = (perf_counter() - start) * 1000
    _emit_profile_generated(profile, duration_ms, max_rows)
    return profile


@app.post("/profile", response_model=DatasetProfile)
async def profile_raw(
    request: Request,
    dataset_name: Optional[str] = Query(None, description="Override dataset label"),
    max_rows: Optional[int] = Query(
        None,
        description="Deterministic sample size if dataset exceeds this many rows",
        ge=1,
    ),
) -> DatasetProfile:
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Request body was empty")
    label = dataset_name or "uploaded"
    start = perf_counter()
    with TRACER.start_as_current_span("profile.raw") as span:
        span.set_attributes(
            {
                "csv_profiler.input_type": "raw",
                "csv_profiler.max_rows": max_rows if max_rows else -1,
            }
        )
        try:
            profile = profile_csv_bytes(
                content,
                label,
                options=_options(max_rows),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    duration_ms = (perf_counter() - start) * 1000
    _emit_profile_generated(profile, duration_ms, max_rows)
    return profile


__all__ = ["app"]
