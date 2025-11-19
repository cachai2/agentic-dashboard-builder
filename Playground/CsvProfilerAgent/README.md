# CSV Profiler Agent Playground

## Objective

Prototype the ingestion + lightweight analysis loop that powers the Agent Framework orchestrator. This sandbox should: (1) accept a CSV (local file path or uploaded bytes), (2) emit the compact profiling JSON described in `README.md` Section 6, and (3) log structured events the orchestrator will consume later.

## Deliverables

1. Minimal FastAPI (or CLI) entry point that accepts a CSV path and returns the profile JSON.
2. Deterministic profiling helpers that cover: dtype inference, null %, distinct count, sample stats for numerics, and categorical top-k suggestions.
3. Contract tests (`tests/test_profile_contract.py`) that assert compliance with `schemas/dashboard_plan.schema.json` inputs.
4. Telemetry hook that emits `profile_generated` with latency + column counts (can be console logs for now).

## Suggested Layout

```text
Playground/CsvProfilerAgent/
├─ app/
│  ├─ main.py            # FastAPI surface or CLI entry
│  ├─ profiling.py       # pure functions for stats
│  └─ schemas.py         # pydantic models mirroring Section 6
├─ tests/
│  └─ test_profile_contract.py
├─ samples/              # copy of repo-level CSVs you need
└─ requirements.txt      # prefer keeping deps lightweight

## Sample Data Sets

- See `docs/datasets.md` for 10k-row-friendly public sources (retail, telco churn, Citi Bike).
- Run `python scripts/generate_sample_datasets.py` to rebuild the deterministic CSVs under `samples/`.
- Each generator produces exactly 10,000 rows so contract tests have predictable runtimes.

## Profiling vs. LLM Responsibilities

- Keep the CSV → profile JSON path deterministic so we always emit the schema referenced in Section 6 / `schemas/dashboard_plan.schema.json`.
- Use LLMs only *after* profile generation (e.g., summarizing anomalies, proposing dashboard focus areas, annotating semantic column hints) to avoid contract drift.
- If we experiment with LLM-derived context, store it separately (e.g., `llm_annotations`) and never mutate the canonical profile payload.
- Deterministic profilers should handle arbitrary CSV schemas by inferring column types, null %, distinct counts, etc., while template adapters map those stats into the fixed JSON.
- This split lets contract tests remain reproducible while still giving Agent Frameworks narrative insights from models when needed.
```

## Sampling Controls

- All profiling surfaces accept an optional `max_rows` parameter; when present and lower than the CSV size we run stats against a deterministic sample taken with a fixed seed.
- Responses include `row_count`, `sampled_row_count`, and `sampling_ratio` so downstream agents can reason about coverage.
- Sampling hooks apply uniformly to path-based runs, multipart uploads, and raw `text/csv` bodies sent to `/profile`.
- Telemetry events (`profile_generated`) now emit `sample_applied`, `sampled_row_count`, `sampling_ratio`, and the requested `max_rows` hint so downstream agents can observe how the profile was built.

## Tracing & Observability

- FastAPI requests and profiling operations emit OpenTelemetry spans (`csv-profiler-agent` service name) with dataset size, sampling flags, and runtimes.
- By default spans go to the console exporter; set `OTEL_EXPORTER_OTLP_ENDPOINT` (and optionally `OTEL_EXPORTER_OTLP_INSECURE=true`) to stream them to an OTLP collector.
- Example launch with OTLP export:

   ```powershell
   $env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318/v1/traces"
   uvicorn app.main:app --port 8101 --reload
   ```

## Integration Guidance

- Keep function signatures aligned with `app/profiling.py` so we can drop this module into the main service unchanged.
- When adding new metrics, update `README.md` Section 6 and create a migration note in `docs/agents/profiling.md` so other copilots learn about the change.
- Return floats/ints, never NumPy types; Agent Framework serialization requires built-in JSON types.
- Provide a `make profile` (or `poetry run profile`) command to simplify local testing.

## Stretch Goals

- Add sampling logic for big CSVs (>100k rows) with reproducible seeds.
- Produce correlation hints (top N pairs) in a separate optional block.
- Emit OpenTelemetry traces so the orchestrator can stitch ingestion + planning spans.

## Local Testing

1. Create a virtual environment and install deps:

   ```powershell
   cd Playground/CsvProfilerAgent
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Launch the FastAPI surface on port `8101` so other agents know where to reach it:

   ```powershell
   uvicorn app.main:app --port 8101 --reload
   ```

3. POST any CSV in `samples/` to `http://localhost:8101/profile` (raw body) or `/profile/upload` (multipart) to verify deterministic JSON output. Example raw-body invocation with sampling:

   ```powershell
   Invoke-WebRequest `
     -Uri "http://localhost:8101/profile?dataset_name=retail_superstore&max_rows=1000" `
     -Method Post `
     -InFile .\samples\retail_superstore_sample.csv `
     -ContentType 'text/csv'
   ```

4. Run contract tests locally before merging changes:

   ```powershell
   pytest
   ```
