# Ignite Demo: Automatic Dashboard Generation Platform (Azure Container Apps + Serverless GPU SLM)

## 1. Vision
Upload a CSV → Automatic EDA profiling → Small Language Model (SLM) plans a dashboard → Backend renders Plotly charts → User views a complete, insight-oriented dashboard. No chat UX; pure “Upload → Dashboard”.

## 2. High-Level Architecture
```
[ Browser Frontend ]
    |  CSV upload / generate request
    v
[ ACA CPU App (FastAPI) ]
    - /upload (ingest + store)
    - /profile (EDA summary via profiling libs)
    - /dashboard/plan (invoke GPU SLM planner)
    - /dashboard/view (render Plotly/HTML)
        |
        | Calls
        v
[ ACA GPU App (SLM Planner Service) ]
    - /plan_dashboard or /chat/completions
    - Runs small model (phi-3 / phi-4 / llama 3 small) on serverless GPU

[ Data Layer ]
  - CSV -> Blob Storage or Azure Files (optionally DuckDB per session)
  - In-memory DataFrame (ephemeral)

[ Observability ]
  - Application Insights: latency, GPU utilization, plan generation counts

[ (Optional) Future Services ]
  - Auth (AAD / Entra ID)
  - Caching layer (Redis) for repeated plans
  - Long-term artifact store (dashboard specs)
```

### Component Roles
- **Frontend**: Minimal form/UI for upload & display. Could be Static Web App calling backend.
- **CPU App (ACA)**: Orchestrates CSV ingestion, profiling, plan invocation, rendering.
- **GPU App (ACA)**: Stateless SLM planner. Scales to zero when idle; returns strictly JSON `DashboardPlan`.
- **Profiling Engine(s)**: ydata-profiling, Lux, AutoViz (metadata + recommendations). Potential to chain multiple.
- **Rendering Layer**: Plotly (interactive). Could later support Altair, Grafana JSON, Power BI Embedded.

## 3. Detailed Flow
1. User uploads CSV → `POST /upload` returns `session_id`, column list, counts.
2. CPU app runs lightweight profiling (`generate_profile_summary`) and optionally deep profiling libs.
3. CPU app calls GPU SLM planner with structured metadata → receives `DashboardPlan` JSON.
4. CPU app renders charts per plan → HTML bundle served by `GET /dashboard/view`.
5. (Optional) Persist plan + rendering artifacts for versioning / audit.

## 4. DashboardPlan JSON Schema (Excerpt)
Core structure returned by SLM (simplified excerpt):
```json
{
  "title": "...",
  "description": "...",
  "priority": "overview | deep-dive | data-quality",
  "sections": [
    {
      "title": "Section Title",
      "charts": [
        {
          "id": "rev_timeseries",
          "type": "line | bar | scatter | box | histogram | heatmap | table | kpi",
          "query": {
            "operation": "timeseries_agg | groupby_agg | topk | distribution | correlation_matrix | outliers",
            "x": "order_date",
            "y": "revenue",
            "agg": "sum | avg | count | min | max | median",
            "time_grain": "day | week | month | quarter | year"
          },
          "insight": "Human-readable rationale"
        }
      ]
    }
  ]
}
```
Full schema lives in `More Specific Architecture.md`.

### SLM Guardrails
- Must not invent columns not in profiling schema.
- Return strictly valid JSON (schema enforcement + retry if malformed).
- Optional: JSON Schema validation service before rendering.

## 5. JSON Handling & Parsing Considerations
Although `Working with JSON.md` is currently empty, we adopt these rules:
- **Validation**: Apply JSON Schema validation (e.g., `jsonschema` lib) on every returned plan.
- **Strict Types**: Enforce enumerations (chart types, operations, aggregations) to avoid injection-like unexpected instructions.
- **Sanitization**: Reject unknown fields; log anomalies for telemetry.
- **Versioning**: Include a `plan_version` in future schema updates for backward compat.
- **Extensibility**: Allow optional `filters`, `group`, `top_k` without breaking base rendering logic.
- **Error Strategy**: If parsing fails → attempt one structured retry with SLM; if still invalid → downgrade to a minimal fallback dashboard (basic summary charts).
- **Security**: Never execute code from JSON. Treat it as declarative spec only.

## 6. Key Profiling Metadata (Inputs to SLM)
- Column schema (name, dtype, null %, distinct count)
- Basic distribution stats (min/max/mean for numerics)
- Time-series detection (presence of datetime-like column)
- Correlations (top N pairs above threshold)
- High-cardinality categorical detection (for limiting bar counts)
- Outlier markers (e.g., IQR method) to justify `box` or `scatter` with highlight.

## 7. Recommended OSS Repos to Leverage
Automatic EDA / Visualization:
- `ydata-profiling` – deep HTML profiling; metadata extraction baseline.
- `AutoViz` – rapid multi-plot generation (distribution, time-series, group-bys).
- `SweetViz` – attractive comparative profiling (optional for diffing source vs target dataset).
- `Lux` – context-aware visualization suggestions directly from DataFrame.
- `DataPrep.EDA` – performant profiling (correlations, type inference).
- `Deepchecks` – data validation & quality insights.
LLM/Agent + Data Patterns:
- `gpt-pilot-eda` – auto-generated EDA scripts.
- `pandas-ai` – LLM-driven dataframe analysis & charts.
- `auto-analyst` – dataset → insights pipeline.
- `genie` – LLM-powered SQL, chart code generation.

Combination Strategy for Demo:
1. Use `ydata-profiling` + `Lux` for metadata and suggestion features.
2. SLM (phi-3 / phi-4 small) for plan JSON on ACA GPU.
3. Plotly for rendering interactive visual layer.

## 8. Azure Container Apps & Serverless GPU Strategy
- **Two-Container Pattern** (recommended): CPU orchestration app + GPU planner app in same ACA Environment.
- **Workload Profiles**: Use GPU workload profile for SLM service (enable scale-to-zero). CPU app on standard profile.
- **Scaling Rules**: HTTP concurrency / RPS autoscaling; set min=0 (GPU), max tuned per cost tolerance.
- **Networking**: Internal service-to-service calls via environment DNS; optionally restrict GPU endpoint with internal ingress only.
- **Authentication**: Managed Identity for accessing Blob, Key Vault (no secrets in code).
- **Observability**: Application Insights custom events: `plan_request`, `plan_latency_ms`, `charts_count`.
- **Cost Control**: Short-lived GPU invocations; consider caching identical plan inputs (same schema + stats) to avoid recompute.
- **Security**: Never allow arbitrary prompt injection via user-supplied text fields; only structured metadata forwarded.

### Microsoft Agent Framework Integration Plan

- **Why**: Using [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview) lets us model the planner/orchestrator as a first-class agent graph with built-in state, tool routing, and evaluation harnesses while remaining open-source friendly ([GitHub repo](https://github.com/microsoft/agent-framework)).
- **Architecture Impact**:
  - The ACA CPU app that currently hosts FastAPI becomes the Agent Framework host process. We embed the framework’s `Agent`, `Tool`, and `Runtime` primitives and expose HTTP endpoints for the frontend to call.
  - Each tool (profiling, GPU planner, rendering, storage access) is wrapped as an Agent Framework `ToolContract`. The GPU ACA app is invoked via a tool adapter so the framework can reason about availability/retries.
  - Session state persists through the framework’s state store abstraction. For now we can use in-memory state backed by Redis/Azure Cache when scaling out; Blob/File storage still captures large artifacts (CSV, generated dashboards).
  - Evaluation and tracing hooks from the framework route into Application Insights so we correlate agent spans with ACA logs.
- **Readme To-Dos**:
  1. Update the CPU app scaffolding to include Agent Framework packages (pip install from GitHub, add to requirements).
  2. Document how to launch the orchestrator locally (`python -m agent_framework run`) once scaffolded.
  3. Define our agent graph (Frontend Agent → Planner Agent → GPU Tool) under `agents/` with prompt assets in `prompts/` for clarity.
  4. Add FAQ entry on why we chose Agent Framework vs bespoke orchestration.
- **Next Architectural Review**: When we reintroduce VNet/private endpoints we should also decide whether to move Agent Framework state storage (Redis/Cosmos) inside the network boundary and whether to host evaluation pipelines separately.

## 9. Deployment / Infra Considerations

- Use Bicep or `azd` to provision:
  - ACA Environment
  - Two Container Apps (cpu-app, gpu-planner)
  - Storage (Blob or Files) + Key Vault + App Insights
- GPU app image must expose only required endpoints; keep model weights local or attached persistent volume if large.
- Validate port alignment (container exposed vs app config) per ACA best practices.
- Use Managed Identity for Blob read/write; store connection strings only if unavoidable (prefer SAS generation via identity).
- Apply resource limits (CPU/memory) to avoid noisy-neighbor effects.

## 10. Rendering Layer Notes

- Start with inline Plotly HTML bundling (`include_plotlyjs='cdn'`).
- Abstract rendering so future adapters (Grafana, Power BI Embedded) can map plan objects to provider-specific spec.
- Consider adding KPI widget type (single-value cards) for aggregated metrics early in dashboard.

## 11. Telemetry & Metrics

| Metric | Source | Purpose |
|--------|--------|---------|
| plan_latency_ms | CPU app timing around SLM call | Performance tuning |
| gpu_utilization | ACA metrics / Azure Monitor | Capacity planning |
| charts_per_plan | Derived from JSON | Complexity/UX insight |
| invalid_plan_retry_count | Validation layer | Model reliability |
| upload_to_first_byte_ms | End-to-end time | Demo wow factor |

## 12. Error Handling Strategy

- 400: Invalid file type / missing session.
- 422: Invalid DashboardPlan JSON schema.
- 500: Profiling failure / GPU planner unavailable.
- Fallback: Minimal dashboard (top numeric distributions + row count).

## 13. Security & Compliance

- No PII retention beyond session unless explicitly persisted.
- Potential anonymization step for columns matching sensitive patterns.
- Key Vault for secrets (if any third-party API keys introduced later).
- Entra ID integration for multi-user enterprise demo (future).

## 14. Performance Optimizations (Roadmap)

- Incremental profiling (sample first; full profile async if > N rows).
- DuckDB pushdown queries for heavy group-bys.
- Cache correlation matrix if repeated for same dataset.
- Precompile common chart specs to reduce render latency.

## 15. Open Questions

1. Should plans be persisted for audit/versioning? If yes, where (Blob vs Cosmos DB)?
    1. No need for initial mvp
1. Multi-tenancy: session isolation strategy (separate storage containers vs prefixing)?
    1. No need
1. Max dataset size target for demo (row count upper bound)?
    1. We can start fairly small (10k rows) to keep profiling fast
1. GPU sizing: smallest SKU sufficient for chosen SLM? Need quantization? FP16 vs INT4?
    1. We'll use A100 GPU with 80GB GPU memory and 1 GPU
1. Schema evolution: support incremental updates when a new CSV with similar columns arrives?
    1. Not in initial demo scope
1. Guardrails: how strict should JSON validation be (reject entire plan vs drop invalid charts)?
    1. drop invalid charts. We should be clear when we try to generate and fail though
1. Data privacy: implement opt-in column masking for high-risk names ("email", "ssn")?
    1. Not in scope
1. Cost optimization: cache identical schema stats → skip planner invocation?
    1. Not in scope
1. Extensibility: plugin system for new `operation` types? (e.g., anomaly detection)
    1. Not in scope
1. Observability: do we need distributed tracing (OpenTelemetry) across CPU↔GPU apps?
    1. Not in scope
1. Authentication: public demo vs authenticated enterprise variant?
    1. Not in scope
1. Resilience: retry policy and circuit breaker thresholds for GPU planner outages?
    1. Not in scope
1. Rollback: versioning of SLM prompt/system prompt—track changes?
    1. YEs please

## 16. Demo Walkthrough (Condensed Script)

1. Introduce problem: manual dashboarding time vs automation.
2. Upload dataset (sales sample) → show immediate profiling output (column list).
3. Click “Generate Dashboard” → narrate profiling → SLM planning → rendering.
4. Scroll through insights; highlight trend/outlier automation.
5. Emphasize ACA serverless GPU scaling & cost efficiency.
6. (Optional) Upload second dataset to prove adaptability.

## 17. Next Steps

- Implement JSON Schema validation module.
- Integrate ydata-profiling + Lux for richer metadata.
- Deploy dual-app ACA environment (cpu + gpu) via Bicep/azd.
- Add caching layer for repeated plan requests.
- Harden system prompt & add retry logic.

## 19. Supported CSV Types (MVP Scope)

Initial focus is on three representative dataset categories to prove flexibility:

- **Revenue / Sales**: Columns like `order_date`, `region`, `category`, `revenue`, `customer_id`. Emphasis on time-series + segment aggregations.
- **Medical (De-identified)**: Columns such as `visit_date`, `procedure_code`, `diagnosis_code`, `length_of_stay`, `cost`. We treat all identifiers as dimensions and avoid PHI; no masking logic in MVP beyond ignoring obviously personal columns.
- **Supply Chain / Inventory**: Columns like `timestamp`, `sku`, `warehouse`, `quantity`, `lead_time_days`. Highlight stock movement trends and top-k SKU distributions.

MVP ingestion heuristics kept intentionally generic (dtype inference, null %, cardinality). Domain-specific tagging & masking deferred to Hardening phase.

### MVP CSV Handling Rules

- Load full file if rows ≤ 100k; else sample first 50k for profiling, keep full for rendering heavy aggregations.
- Detect datetime columns (parseable ISO / common date formats) → enable at least one timeseries chart.
- If categorical distinct count > 100, avoid full bar plot; prefer `top_k` (e.g., top 20 by aggregate metric).
- Treat unknown string-heavy columns with near-unique values as identifiers (avoid plotting directly).

## 20. Architecture Separation: MVP vs Hardening

### MVP (2-day target)

- Basic FastAPI services (`/upload`, `/dashboard/plan`, `/dashboard/view`).
- Simple profiling (`generate_profile_summary`) with stats: null %, distinct count, dtype.
- Minimal SLM prompt + single retry on invalid JSON.
- Rendering for a subset of operations: `timeseries_agg`, `groupby_agg`, `distribution`, `outliers` (simple box plot fallback).
- Basic HTML dashboard layout with Plotly inline.
- Application Insights instrumentation: latency + plan request count.

### Hardening / Post-MVP Enhancements

- Advanced profiling pipeline (ydata-profiling + Lux + correlations + outlier detection heuristics).
- Role inference (metric vs dimension vs identifier) & semantic/unit tagging.
- PII/PHI masking layer for medical datasets (regex + hash tokens).
- High-cardinality strategy (auto top_k, clustering, dimensional reduction options).
- JSON Schema enforcement + recoverable chart-level rejection (drop invalid chart, keep rest).
- Caching of plan results keyed by schema signature.
- GPU planner circuit breaker + exponential backoff retries.
- Pluggable renderer adapters (Grafana JSON, Power BI) via an abstraction layer.
- Prompt versioning + audit trail (persist system prompt & plan JSON).
- Optional domain adapters folder (`app/domain_adapters/*.py`).

## 21. Modularity & Reuse Strategy

Design layers to avoid rewriting for Hardening:

- **Ingestion Layer**: Wrapper function returning a DataFrame + lightweight metadata. Replace internals (sampling, delimiter detection) without changing caller.
- **Profiling Pipeline**: Registry pattern (`profilers = [basic_stats, correlations, lux_adapter]`) producing a merged JSON profile. Hardening adds modules without altering interface.
- **Planning Interface**: `plan_dashboard(profile_summary) -> DashboardPlan`. Implementation can shift from local SLM to Azure AI endpoint transparently.
- **Rendering Layer**: Accepts canonical `DashboardPlan` so new chart types or providers extend via strategy objects (e.g., `renderers[type]`).
- **Validation Layer**: Central JSON schema check; later can add chart-level sanitizers while preserving main contract.
- **Config / Feature Flags**: Single `settings.py` or env-based toggles to enable domain adapters post-MVP.

## 22. Two-Day Build Feasibility & Plan

Yes: a functional MVP (upload → plan → render) is achievable in two focused days. Hardening items will extend beyond.

### Day 1

- Scaffold FastAPI CPU app endpoints.
- Implement basic profiling (`generate_profile_summary`).
- Draft SLM planner stub (can mock response before GPU integration).
- Implement rendering for `timeseries_agg` and `groupby_agg`.
- Integrate Application Insights logging stubs.
- End-to-end local test with a revenue CSV.

### Day 2

- Add `distribution` & simple `outliers` support.
- Add JSON validation + retry logic.
- Containerize CPU app; create GPU planner container (mock or minimal model).
- Deploy to ACA (environment + two apps) using basic Bicep/azd.
- Test second dataset type (medical de-identified sample) + supply chain sample.
- Polish README + demo script.

### Risks / Mitigations

- GPU provisioning delay: Mitigate by mocking planner early; switch to real SLM when GPU ready.
- Invalid model outputs: Start with very constrained system prompt; fallback to baseline dashboard.
- Large CSV performance: Use sampling; document size limits in README.
- Time overruns on deployment: Prioritize local functional demo first; treat ACA deployment as stretch for afternoon of Day 2.

### Out-of-Scope for 2 Days (Flagged for Hardening)

- Full domain adapters, PHI masking, correlation matrix logic, caching, advanced scaling policies.

## 23. Future Hardening Checklist (Roll-in After Demo)

- [ ] Add domain adapters (revenue/medical/supply chain) with tagging.
- [ ] Implement PII/PHI masking & consent toggle.
- [ ] Correlation + anomaly detection operations.
- [ ] Plan caching + schema hashing.
- [ ] Renderer abstraction supporting Power BI / Grafana.
- [ ] Prompt + plan version audit log.
- [ ] GPU autoscale tuning & cost metrics dashboard.
- [ ] High-cardinality dimensional reduction (sampling, clustering).
- [ ] Extended error taxonomy (planner vs render vs profiling).

## 24. Implementation Task Plan (Detailed Execution Roadmap)

### Phase 0: Bootstrap & Environment

- [ ] Create repo structure (`app/`, `infra/`, `tests/`, `scripts/`).
- [ ] Initialize Python project (`pyproject.toml` or `requirements.txt`).
- [ ] Add `settings.py` for feature flags (e.g., `ENABLE_LUX`, `ENABLE_ADV_PROFILING`).
- [ ] Decide local dev data storage (temp folder vs DuckDB file).
- [ ] Draft system prompt file (`prompts/system_planner.txt`) with version tag.

### Phase 1: Core Ingestion & Profiling (MVP)

- [ ] Implement `/upload` endpoint (FastAPI) reading CSV via streaming -> pandas.
- [ ] Add delimiter & encoding detection fallback (`csv.Sniffer` + `chardet`).
- [ ] Implement `generate_profile_summary` (basic stats, dtype, distinct, null%).
- [ ] Add sampling logic for large files (configurable row threshold).
- [ ] Unit tests for profile summary on sample revenue, medical, supply chain CSVs.

### Phase 2: Planner Integration (Mock → Real)

- [ ] Implement `plan_dashboard(profile_summary)` mock returning fixed plan for initial testing.
- [ ] Define JSON Schema file (`schemas/dashboard_plan.schema.json`).
- [ ] Add validation function (`validate_plan(plan_dict)`).
- [ ] Integrate retry logic on invalid JSON (1 retry then fallback plan).
- [ ] Replace mock with real SLM call (HTTP client to GPU app or Azure AI) behind interface.
- [ ] Track prompt + response (sanitized) for audit (log & optional storage).

### Phase 3: Rendering Layer

- [ ] Implement chart rendering functions for: `timeseries_agg`, `groupby_agg`, `distribution`, `outliers` (basic box plot).
- [ ] Add top_k support when specified.
- [ ] Create HTML template using Jinja2 with section grouping.
- [ ] Fallback renderer when plan invalid (basic summary charts).
- [ ] Snapshot tests (e.g., assert presence of expected chart IDs in HTML).

### Phase 4: GPU Planner Service (Separate ACA App)

- [ ] Scaffold minimal FastAPI GPU service (`/plan_dashboard` or OpenAI-style `/chat/completions`).
- [ ] Containerize with base image, include model weights (or configure Azure AI endpoint credentials via Managed Identity / Key Vault).
- [ ] Add health endpoint & readiness probe.
- [ ] Implement simple concurrency guard (semaphore) if local hosting.
- [ ] Logging of request size + latency + truncated prompt.

### Phase 5: Telemetry & Observability

- [ ] Integrate Application Insights SDK (request traces + custom events).
- [ ] Emit events: `plan_request`, `plan_success`, `plan_retry`, `plan_fallback`.
- [ ] Add timing metrics (upload->plan, plan->render).
- [ ] Optional: simple metrics endpoint (`/metrics` for internal scraping) if needed.

### Phase 6: Deployment (ACA + Infra)

- [ ] Author Bicep/azd templates under `infra/` (environment, cpu-app, gpu-app, storage, key vault, app insights).
- [ ] Validate deployment with `az deployment what-if` or `azd provision --preview`.
- [ ] Configure ingress (public for CPU app, internal for GPU app).
- [ ] Bind Managed Identity to Blob + Key Vault access policies (no hardcoded secrets).
- [ ] Smoke test in ACA: upload + generate plan + view dashboard.

### Phase 7: Data Variety Validation

- [ ] Run revenue CSV through full pipeline (ensure timeseries + segment charts).
- [ ] Run de-identified medical CSV (avoid PHI exposure, still produce metrics).
- [ ] Run supply chain CSV (top_k SKU + inventory trend).
- [ ] Document limitations (e.g., extremely wide tables, multi-sheet imports).

### Phase 8: Hardening Prep (Post-Demo Hooks)

- [ ] Add profiler registry abstraction (`profilers/` folder).
- [ ] Stub domain adapter interface (`domain_adapters/base.py`).
- [ ] Create feature flag path for enabling PHI masking later.
- [ ] Persist prompt & plan version metadata (e.g., JSON lines in Blob or table storage).

### Phase 9: Quality & Risk Mitigation

- [ ] Add integration tests (end-to-end temp server run -> assert HTML output).
- [ ] Implement graceful degradation if GPU planner unreachable (auto fallback plan).
- [ ] Track invalid chart rejection count for future tuning.
- [ ] Security review: ensure no raw row samples logged.

### Phase 10: Demo Packaging

- [ ] Produce demo script markdown (`demo/ignite_walkthrough.md`).
- [ ] Add sample datasets folder (`samples/`).
- [ ] Record latency targets vs actual (table in README or metrics dashboard link).
- [ ] Final README cleanup & link to repos + architecture diagram.

### Phase 11: Stretch / Optional Before Ignite

- [ ] Basic correlation matrix support.
- [ ] KPI card aggregation (sum revenue, row counts, etc.).
- [ ] Plan caching (schema signature hash).
- [ ] Simple anomaly op (z-score threshold).

### Responsibility Mapping (RACI Style - Optional)

| Area | Primary | Support |
|------|---------|---------|
| Ingestion/Profiling | Backend Eng | Data Eng |
| Planner Service | ML Eng | Backend Eng |
| Rendering | Frontend/Fullstack | Design |
| Infra & ACA | DevOps | Security |
| Telemetry | DevOps | Backend Eng |
| Validation/Schema | Backend Eng | ML Eng |
| Demo Script | PM/Developer Advocate | Engineering |

### Success Criteria

- < 5s end-to-end for 10k-row CSV (local or ACA test).
- Valid JSON plan on first attempt ≥ 90% of trials.
- Dashboard includes at least: one timeseries, one distribution, one segment comparison.
- No PHI or PII strings in logs.
- Clean fallback behavior demonstrated live.

## 25. Copilot Collaboration Guide

### 25.1 Shared Working Agreements

- Keep feature work on short-lived branches (`feature/<area>-<initials>`). Rebase daily to avoid Copilot collision and open PRs with scope + contract changes clearly summarized.
- Always patch interface docs first: update `schemas/dashboard_plan.schema.json`, `app/README` (future), or this file before modifying dependent services so other copilots ingest the latest contracts via context.
- Include a `copilot-notes.md` snippet in each PR summarizing generated code blocks, assumptions, and manual edits—makes it easy for concurrent copilots to pick up threads.
- Use GitHub Projects (or Issues) to assign each copilot to one of the four agents (Upload, Profiling, Planning, Rendering) or to infra/telemetry. Reference issue IDs in commit messages for traceability.
- Favor Managed Identity + config files over secrets for local testing; never paste tenant-specific credentials into prompts so multiple copilots can work safely.

### 25.2 Agent-Specific Instructions

| Agent | Primary Scope | Key Files | Copilot Notes |
|-------|---------------|-----------|---------------|
| Upload Orchestrator | `/upload`, storage hand-off, correlation IDs | `app/main.py`, `app/profiling.py`, `samples/`, `docs/agents/upload-orchestrator.md` | Maintain `session_id` contract and keep profiling response schema stable. Coordinate changes to `generate_profile_summary` with planner team before merging. |
| Profiling Pipeline | Column stats, dtype inference, risk flags | `app/profiling.py`, future `profilers/`, `docs/agents/profiling.md` | Emit deterministic JSON so caches are reusable; when adding new metrics update Section 6 + schema docs. |
| Planning Agent (GPU) | JSON `DashboardPlan` output, prompt files | `app/planner.py` (mock), future `planner_service/`, `docs/agents/planner.md` | Treat system prompt as versioned asset. Log prompt hash + correlationId for observability. |
| Rendering Agent | Plotly chart mapping + HTML | `app/render.py`, templates, `docs/agents/rendering.md` | Add new chart types via renderer registry and document supported operations before exposing them to planner prompts. |
| Infra & Observability | ACA env, identities, logging | `infra/main.bicep`, `azure.yaml` | Run `bicep build` or `azd provision --preview` after every change. Maintain tags/outputs per Azure IaC rules. |

### 25.3 Infra Snapshot for Copilots

- `infra/main.bicep` currently provisions: User-Assigned Managed Identity, Log Analytics workspace, Azure Container Registry (with AcrPull role grant), Storage Account (shared key + public access disabled), Key Vault with purge protection, ACA Environment, and two Container Apps (`cpu-app`, `gpu-planner`).
- Container Apps reference the Microsoft hello-world image as a placeholder; update Dockerfiles + azd config before first shared deployment.
- `azure.yaml` defines two services so each copilot can run `azd up` scoped to their area without touching the other container unless intended.

### 25.4 Prerequisites Before Running 4–5 Copilots

1. **Lock Contracts**: Freeze the `DashboardPlan` schema and profile summary JSON with version tags; publish delta notes so copilots know when breaking changes occur.
2. **Instruction Files**: Add lightweight `CONTRIBUTING.md`, `/app/README.md`, and `/infra/README.md` excerpts that restate guardrails so each copilot’s chat history includes them.
3. **Branch + Environment Matrix**: Create environment aliases via `azd env new <name>` (e.g., `cpu-dev`, `gpu-dev`, `infra-playground`) so simultaneous deployments don’t collide.
4. **CI/Lint Hooks**: Enable GitHub Actions (lint + tests + `bicep build`) to give quick feedback on Copilot-generated code before merge.
5. **Dataset + Secrets Vault**: Store shared sample CSVs in `samples/` and configure Key Vault secrets/managed identity assignments so every copilot has the same dev baseline.
6. **Communication Loop**: Stand up a short daily sync or Slack channel (#ignite-dashboard) where copilots post what they touched; include correlation IDs or PR links for cross-team visibility.
7. **Testing Harness**: Finish minimal integration tests (upload → plan → render) so copilots can verify their changes quickly before handing off.

### 25.5 Repo Duplication Workflow

When multiple VS Code instances cannot open the same local folder, give each agent its own clone while keeping upstream history consistent.

1. Pick a parent directory (e.g., `C:\Users\cachai\demos`) and run one of:

```powershell
cd C:\Users\cachai\demos
git clone <repo-url> ignite-25-fresh-upload
git clone <repo-url> ignite-25-fresh-profiling
git clone <repo-url> ignite-25-fresh-planner
git clone <repo-url> ignite-25-fresh-rendering
```

Or, from an existing clone use `git worktree` to share objects:

```powershell
cd C:\Users\cachai\demos\ignite-25-fresh
git worktree add ..\ignite-25-fresh-upload main
git worktree add ..\ignite-25-fresh-profiling main
```

1. Assign each VS Code/Copilot window one folder. Work on feature branches (`feature/<agent>-<topic>`), commit locally, then push to the shared remote.
2. Keep clones in sync by running `git pull --rebase origin main` daily and opening PRs from each feature branch.
3. Document which clone tackles which agent in #ignite-dashboard so no two copilots use the same working copy accidentally.

### 25.6 Playground Modules & Ownership

Use the `Playground/` directory for isolated Copilot experiments. Each subfolder has its own README with scope, deliverables, and stretch ideas so copilots can iterate independently before code graduates into `app/`.

| Playground Folder | Focus | Primary Questions Answered | Feeds Into |
|-------------------|-------|----------------------------|------------|
| `Playground/CsvProfilerAgent` | CSV ingestion + profiling summaries | Can we deterministically infer schema + stats fast enough for GPT planning? | Agent Framework CPU orchestrator (`generate_profile_summary`) |
| `Playground/OllamaStructuredJson` | GPU/Ollama prompt craft + schema-safe JSON | Can Ollama (or other SLMs) emit valid `DashboardPlan` consistently? | GPU Container App + planner tool contract |
| `Playground/ChartRenderingAgent` | Plotly/HTML layout engine | Does the rendered dashboard honor every chart type & insight from the plan? | Frontend embedding + future renderer registry |
| `Playground/FrontendAgent` | Upload UX + dashboard viewer | What end-to-end UX feels right before wiring real APIs? | Public ACA frontend / Static Web App |

We will likely add a fifth sandbox for experimenting with prebuilt chart-generation frameworks (e.g., AutoViz, Deepchecks Viz, Plotly Express templates) so copilots can compare off-the-shelf builders against the bespoke renderer. See Section 25.7 once created.

#### Workflow

1. Clone or open the repo in a new VS Code window and change into the module folder (e.g., `cd Playground/CsvProfilerAgent`).
2. Follow the README inside the module to install dependencies (`pip install -r requirements.txt`, `npm install`, etc.).
3. Keep experiments self-contained; once stable, upstream contracts to `app/` via PRs that reference both the main repo and the module folder.
4. Log outcomes or open issues referencing the module so other copilots know the state of each sandbox.

### 25.7 Prebuilt Chart Builder Experiments

- Goal: Evaluate OSS/commercial chart-builder libraries (AutoViz, Deepchecks Viz, ydata-profiling visuals, etc.) as a potential acceleration path for the rendering layer.
- Action: Create `Playground/PrebuiltChartGenAgent/` with instructions for wiring external tooling, comparing output fidelity to our canonical renderer, and documenting trade-offs (load time, configurability, license implications).
- Outcome: Decide whether the production renderer should keep custom Plotly code, embed a third-party builder wholesale, or mix (e.g., use AutoViz for quick distributions but custom layout for KPIs).

## 26. GPT-5 Agent Orchestrator Setup

Use this checklist when we are ready to swap the mock planner for a GPT-5-powered orchestrator that coordinates downstream renderers and profilers.

### 26.1 Prerequisites

1. **Model Access**: Request GPT-5 (or GPT-5-mini) access in Azure AI Foundry or Azure OpenAI. Confirm the model appears in your tenant’s catalog and note the endpoint + deployment name.
2. **Resource Naming**: Decide whether GPT-5 will run via Azure AI Foundry (preferred) or a hosted GPU container. If using Foundry, provision a project + hub in the same region as ACA to minimize latency.
3. **Identity & Secrets**: Ensure the CPU app’s managed identity (or a Key Vault secret) can call the GPT-5 endpoint. Plan for `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, and `AZURE_OPENAI_API_VERSION` env vars.
4. **Networking**: If calling GPT-5 privately, set up VNet integration or a private endpoint for the Foundry project.
5. **Prompt Assets**: Create a `prompts/system_gpt5.md` file that captures the orchestrator persona, JSON schema expectations, and strict-mode instructions.

### 26.2 Implementation Steps

1. **Provision Model**

- `az cognitiveservices account create ...` (Azure OpenAI) or `az ai project create ...` (Foundry) to host GPT-5.
- Deploy GPT-5-mini (or full GPT-5 if quota allows) and record deployment name.

1. **Wire Secrets / Identity**

- If using API keys, store them in Key Vault and grant the CPU app’s user-assigned managed identity `get` permissions.
- Alternatively, enable Microsoft Entra auth on the Foundry endpoint so the managed identity can request tokens without secrets.

1. **Update Planner Service**

- Create `planner_service/` (or extend current GPU container) with a FastAPI endpoint that proxies requests to GPT-5 via the Azure OpenAI SDK.
- Add retry logic + structured output enforcement (e.g., `response_format={"type":"json_schema",...}` once available).

1. **Update CPU App Configuration**

- Add new settings in `app/settings.py` (endpoint, deployment, api_version, strict_mode flag).
- In `/dashboard/plan`, call the GPT-5 planner client instead of the mock when `RUN_PLANNER_MOCK` is false.

1. **Infra Adjustments**

- Extend `infra/main.bicep` to inject the new environment variables into both ACA containers and to grant Key Vault access policies if needed.
- If the planner remains a separate ACA GPU app, ensure it reaches the GPT-5 endpoint over HTTPS (outbound rules already allowed by default).

1. **Validation & Guardrails**

- Run `scripts/test_planner.py` (to be created) with sample profiles to verify valid JSON is returned.
- Monitor Application Insights for schema failures, latency > SLA, and token usage; adjust prompts or temperature accordingly.

1. **Release Process**

- Document the GPT-5 deployment in `docs/agents/planner.md` (prompt version, model release date, deployment name).
- Update demo script to highlight “GPT-5 orchestrated planning” and capture before/after metrics.

Following these steps gives every copilot a deterministic path to enable GPT-5 as the orchestrator without blocking on ad-hoc setup.

## 27. azd Up Workflow (Infra Only)

Until the GPT-5/OpenAI resources are ready, you can still provision the shared infrastructure (ACA env, identities, storage, ACR, Key Vault, Log Analytics) via `azd up` using the templates already committed.

### 27.1 One-Time Prep

1. Install [Azure Developer CLI](https://aka.ms/azure-dev/install) and log in:

   ```powershell
   azd auth login
   ```

2. Pick your subscription ID, preferred region (e.g., `eastus2`), and an environment name such as `ignite-shared`.

### 27.2 Provision Steps (without OpenAI)

1. From the repo root, create the environment and pass subscription/location so `infra/main.parameters.json` picks them up:

   ```powershell
   cd C:\Users\cachai\demos\ignite-25-fresh
   azd env new ignite-shared --subscription <SUB_ID> --location eastus2
   ```

2. Run provisioning (this deploys only the Container Apps + support services; no OpenAI resources are declared):

   ```powershell
   azd up
   ```

   - `azd` builds `infra/main.bicep`, creates the resource group, managed identity, ACR, Storage Account (with shared key + public access disabled), Key Vault, Log Analytics, Container Apps Environment, and both container apps (CPU + GPU) pointing to the placeholder images.
   - The GPU app is internal only; the CPU app exposes external ingress on port 8000.

3. Capture outputs (`resourceGroupId`, `acrLoginServer`) from the CLI and store them in your notes or `azd env get-values` for later use when pushing real images.

4. After provisioning, update the container images by running `azd deploy` (once Dockerfiles are ready) or manually tagging/pushing images to the ACR `acrLoginServer` reported in step 3.

### 27.3 Next Steps Post-Provisioning

- Configure OpenAI / GPT-5 credentials manually (see Section 26) and store them in Key Vault or environment secrets through `azd env set` when ready.
- Assign extra RBAC permissions if new services (e.g., Azure AI Foundry) need to access the managed identity.
- Use `azd down` to tear everything down if you need a clean reset.



## 18. References (Repos)

- [ydata-profiling](https://github.com/ydataai/ydata-profiling)
- [AutoViz](https://github.com/AutoViML/AutoViz)
- [SweetViz](https://github.com/fbdesignpro/sweetviz)
- [Lux](https://github.com/lux-org/lux)
- [DataPrep.EDA](https://github.com/sfu-db/dataprep)
- [Deepchecks](https://github.com/deepchecks/deepchecks)
- [gpt-pilot-eda](https://github.com/ninilinux/gpt-pilot-eda)
- [pandas-ai](https://github.com/Sinaptik-AI/pandas-ai)
- [auto-analyst](https://github.com/sail-sg/auto-analyst)
- [genie](https://github.com/vercel-labs/genie)

---
This README is tailored for an Ignite demo: concise narrative, clear GPU/ACA value, and explicit open questions for architectural discussion. Update sections as implementation matures.
