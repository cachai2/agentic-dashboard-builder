# Rendering Agent

## Workspace Setup

- Open the repo root so renderer, schemas, and shared prompts are in scope for Copilot suggestions.
- Primary files: `app/render.py`, future `templates/`, `docs/agents/rendering.md`, and `samples/` for test data.
- Run commands from root (e.g., `pytest`, `uvicorn`) to share the same virtualenv and config.

## 1. Scope & Responsibilities

- Converts validated `DashboardPlan` + DataFrame slices into Plotly figures and HTML bundles.
- Maintains renderer registry for each supported operation (`timeseries_agg`, `groupby_agg`, `distribution`, `outliers`).
- Provides fallback dashboard when plan validation fails or planner unavailable.
- Owns templating (Jinja2) and front-end friendly metadata (chart IDs, section headers).

## 2. Contracts

| Component | Contract |
|-----------|----------|
| Input | `plan` dict (already schema-validated) plus pandas `DataFrame`. |
| Output | HTML string containing Plotly assets + serialized metadata for embedding. |
| Renderer Registry | `render_chart(operation, spec, df)` functions must raise `ValueError` on unsupported combos. |
| Fallback | Provide deterministic minimal dashboard (row count, top numeric distributions) when planner fails. |

## 3. Dependencies & Configuration

- Code resides in `app/render.py` today; future templates under `templates/`.
- Plotly + Jinja2 listed in `requirements.txt`.
- Feature flags can toggle additional chart libraries (Altair, Grafana adapters) once added.

## 4. Run Workflow (Local)

1. Import `render_dashboard` in a notebook or FastAPI route.
2. Feed a known-good plan (see `schemas/dashboard_plan.schema.json` examples) and dataset from `samples/`.
3. Inspect HTML output manually; add snapshot tests (TODO) to catch regressions.

## 5. Observability & Guardrails

- Log chart count, render duration, and list of operations used.
- Ensure no raw data leaks into logs; only aggregate summaries or metadata.
- When a chart spec fails, record the offending `chart_id` and continue if policy allows dropping individual charts.

## 6. Open Threads / TODOs

- Add template overrides for future front-end integration (Static Web App, Power BI embedding).
- Implement top_k support + formatting (currency, percentages) tied to profile hints.
- Introduce screenshot or PDF export hooks once dashboards stabilize.
- Build automated visual regression tests (e.g., Plotly Kaleido snapshots) to validate rendering changes.
