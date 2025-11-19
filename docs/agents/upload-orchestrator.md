# Upload Orchestrator Agent

## Workspace Setup

- Always open the repo root (`ignite-25-fresh`) so schemas, settings, and infra references stay in Copilot context.
- Primary focus paths: `app/main.py`, `app/profiling.py`, `samples/`, and this doc.
- Recommended terminal working dir: repo root (so `uvicorn`, `pytest`, and `azd` commands share the same env).

## 1. Scope & Responsibilities

- Owns `/upload`, `/dashboard/plan`, `/dashboard/view`, `/health` endpoints in `app/main.py`.
- Manages CSV ingestion, storage hand-off, and correlation IDs for downstream agents.
- Orchestrates the full pipeline: profiling → planner → rendering → response packaging.
- Enforces request-level guardrails (file size, type validation, session tracking).

## 2. Contracts

| Component | Contract |
|-----------|----------|
| Input | `multipart/form-data` upload (`file`, optional `dataset_label`). Max size currently governed by FastAPI defaults; document if raising. |
| Profile Request | Calls `generate_profile_summary(df)` and expects dict with fields in Section 6 of README (name, dtype, null_pct, distinct_count, hints). |
| Planner Request | `POST /dashboard/plan`: payload `{ "profile_summary": {...}, "session_id": str }`. Planner response validated against `schemas/dashboard_plan.schema.json`. |
| Rendering Hand-off | Calls `render_dashboard(plan, df)`; expects HTML string and raises exception on unsupported chart types. |
| Storage | Writes original CSV to Blob/Files (future). Until hooked up, data stays in-memory; doc update once storage implemented. |

## 3. Dependencies & Configuration

- `settings.Settings` (env vars): `MAX_PROFILE_ROWS`, `RUN_PLANNER_MOCK`, etc.
- Managed Identity for Storage + Key Vault once infra integrated.
- Azure Application Insights instrumentation (planned) for correlation IDs.
- Feature flags for advanced profiling or planner endpoints should live here.

## 4. Run Workflow (Local)

1. `uvicorn app.main:app --reload`.
2. `POST /upload` with sample from `samples/`.
3. Inspect JSON response for `session_id`, `profile_summary`.
4. `POST /dashboard/plan` (auto-called by `/upload` in future) → ensure schema validation passes or fallback kicks in.
5. `GET /dashboard/view?session_id=...` to render HTML snippet.

## 5. Observability & Guardrails

- Emit `plan_request`, `plan_success`, `plan_fallback` custom events with `correlationId`.
- Reject planner responses that fail schema validation; log offending sections.
- Track profiling + planner latency to surface slow datasets.
- Never log row-level data; only metadata summaries.

## 6. Open Threads / TODOs

- Wire storage persistence (Blob container + SAS/MI path) and update contract doc.
- Add retry/backoff logic for planner outages.
- Document size limits + sampling strategy once finalized.
- Integrate Application Insights + OpenTelemetry exporters for tracing.
