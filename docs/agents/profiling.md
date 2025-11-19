# Profiling Agent

## Workspace Setup

- Open the repository root so `schemas/`, `samples/`, and shared settings stay visible to Copilot.
- Primary focus paths: `app/profiling.py`, future `profilers/` modules, `docs/agents/profiling.md`, and `samples/`.
- Run terminals from the root to access shared virtualenvs/tests (e.g., `python -m pytest tests/test_profiling.py`).

## 1. Scope & Responsibilities

- Converts raw CSVs into deterministic `profile_summary` JSON used by planner and renderer.
- Detects dtypes, cardinality, null %, datetime hints, and risk flags (future PHI detection).
- Applies sampling logic for large files and records sample metadata for reproducibility.
- Provides hooks for multiple profiling backends (basic stats now, ydata-profiling/Lux later).

## 2. Contracts

| Component | Contract |
|-----------|----------|
| Input | Pandas `DataFrame` plus optional context (`dataset_label`, sample metadata). |
| Output | Dict with keys: `columns` (list of `{name, dtype, role_hint, distinct_count, null_pct}`), `row_count`, `sample_rows`, `datetime_columns`, `potential_identifiers`. |
| Storage | Emits serialized JSON attached to session; orchestrator caches in memory or storage. |
| Versioning | Include `profile_version` when the schema changes; bump README Section 6 and notify planner/rendering agents. |

## 3. Dependencies & Configuration

- `app/profiling.py` hosts `generate_profile_summary` baseline.
- Future modules live under `profilers/` (registry pattern) and toggle via `settings.ENABLE_ADVANCED_PROFILING`.
- Requires access to CSV storage (Blob) if profiling is decoupled from upload service.

## 4. Run Workflow (Local)

1. Call `generate_profile_summary(df)` within FastAPI request or standalone notebook.
2. Verify JSON matches schema documented above.
3. Add/adjust heuristics; run unit tests once created (TODO) to ensure consistent ordering and typing.

## 5. Observability & Guardrails

- Log summary stats only—never raw row samples.
- Emit warnings for low-confidence detections (e.g., mixed types, high null %).
- Surface `profile_duration_ms` to Application Insights.
- When new heuristics impact planner prompts, update `docs/agents/planner.md`.

## 6. Open Threads / TODOs

- Implement sampler + metadata (rows_sampled, sampling_strategy).
- Add correlation and outlier hints for planner.
- Integrate PHI/PII detectors for medical datasets (post-MVP).
- Write unit tests covering revenue, medical, supply chain sample CSVs.
