# Agent Service Test Plan

_Last updated: 2025-11-20_

## 1. Objectives
- Verify that the Ollama Structured JSON gateway ("gateway") can reach the GPU-backed Ollama deployment in Azure Container Apps and enforce schema-safe responses.
- Confirm the Agent Orchestrator calls the gateway with the expected payloads, retries, and schema enforcement.
- Exercise the broader agent-service surface (profiling → planning → rendering → artifact handling) to catch regressions before end-to-end demos or deployments.

## 2. Scope
**In scope**
- `app/agent-service/OllamaStructuredJson` FastAPI proxy
- `app/agent-service/AgentOrchestrator` workflows/CLI/API
- Supporting agents invoked by the orchestrator (CSV profiler, rendering adapters, storage tool bridge)
- Observability, configuration, and failure-handling paths for the above components

**Out of scope (covered elsewhere)**
- Frontend React app, unless explicitly interacting with orchestrator APIs
- Azure infrastructure provisioning (`infra/*.bicep`, azd pipelines)
- Model prompt/content validation beyond schema conformance (handled by ML evaluation plan)

## 3. Test Environments

| Env | Description | Target URLs / Notes |
| --- | --- | --- |
| **Local Dev (default)** | Run gateway + orchestrator on developer laptop using Python 3.11+ | `http://127.0.0.1:8801` for gateway, `ORCH_PLANNER_MODE=remote` so requests still hit Azure Ollama |
| **Azure ACA (remote)** | Production-like GPU container for Ollama | `https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io` (`/api/chat`), reachable only when VPN/firewall permits |

> **Planner policy:** All validation runs use the live Azure Ollama deployment only. Keep `OLLAMA_MODE=remote` and `ORCH_PLANNER_MODE=remote`; do not enable local or mock planner modes during this test suite.

## 4. Prerequisites & Instrumentation

- Python env that can run `uvicorn app.service:app` plus orchestrator CLI (`pip install -e app/agent-service/AgentOrchestrator`).
- Azure Container Apps deployment of Ollama reachable via HTTPS; credentials handled by public endpoint for now.
- `schemas/dashboard_plan.schema.json` synced with Azure deployment (validate checksum before tests).
- Logging destinations: local console + `app/agent-service/agent-service/artifacts/` capture; optional Application Insights when configured.
- Diagnostics helpers: `start_gateway.ps1`, `ping_gateway.py`, Postman or `Invoke-WebRequest` for raw HTTP probes.
- Planner mode guardrails: export `OLLAMA_MODE=remote` and `ORCH_PLANNER_MODE=remote` in every terminal; do not override with mock/stub modes while executing this plan.
- **Terminal discipline:** long-lived services (gateway, orchestrator FastAPI app, chaos proxies, contract harnesses) must be launched manually in their own terminals before invoking agent/CLI commands. Each scenario below explicitly labels when to open a dedicated terminal versus running within the primary test terminal. Whenever a scenario asks you to start a `uvicorn` server, pause execution, prompt the operator to start it, and resume only after they confirm the server is running.

## 5. Test Data

| Dataset | Location | Purpose |
| --- | --- | --- |
| Retail Superstore sample | `Playground/CsvProfilerAgent/samples/retail_superstore_sample.csv` | Primary regression dataset exercising wide column variety |
| Citi Bike sample | `app/agent-service/artifacts/citibike/*.csv` | High-cardinality + datetime heavy scenario |
| Telco churn sample | `app/agent-service/artifacts/telco/*.csv` | Classification-style metrics, tests complex prompts |
| Synthetic bad data | Hand-crafted (e.g., null-heavy CSVs) | Negative testing for profiler + schema enforcement |

## 6. Execution Approach

1. Smoke-test environment (`GW-01` / `GW-02`) before running any orchestrator scenarios.
2. Run gateway-focused tests (section 7A) independently so Azure connectivity regressions are isolated fast.
3. Execute orchestrator contract tests (section 7B) with gateway in remote mode; capture HTTP traces.
4. Run extended functionality suites (section 7C) daily; automate critical happy-path flows via pytest or Playwright API tests where possible.
5. Non-functional checks (section 7D) run before every release or infra change.
6. On any failure, capture a single-line summary in the terminal log following this format: `FAIL <TestID> | <Component> | <Command/Endpoint>` (e.g., `FAIL ORCH-02 | gateway-json | python -m agent_orchestrator.cli ...`). Follow up with the stack trace or HTTP payload immediately after so CI logs remain searchable.
7. When a scenario passes, edit the Scenario column in section 7 with a `[success YYYY-MM-DD]` suffix so future runs can skip re-validating already proven steps.

## 7. Test Matrix

### A. Gateway ↔ Azure Ollama Connectivity

| ID | Scenario | Objective | Steps | Expected |
| --- | --- | --- | --- | --- |
| **GW-01** | Environment wiring `[success 2025-11-20]` | Ensure gateway points to Azure host with correct schema + credentials | **Terminal A:** run `start_gateway.ps1`; keep session open while verifying env vars (`OLLAMA_HOST`, `PLAN_SCHEMA_PATH`) and `uvicorn` logs | Gateway starts without config errors; logs show `mode=remote` and schema path resolved |
| **GW-02** | Direct Azure health probe `[success 2025-11-20]` | Confirm ACA app reachable from tester network | Same terminal as probe (no gateway needed): `Invoke-WebRequest https://ollama-ignite-demo-evdeo.../healthz` (or `/api/version` if exposed) | HTTP 200 with model metadata; TLS handshake succeeds |
| **GW-03** | Gateway `/json` happy path | Validate proxy sends request to ACA and returns JSON to caller | **Terminal A:** keep gateway from GW-01 running. **Terminal B:** run `python app/agent-service/ping_gateway.py`; inspect response and gateway logs | `/json` returns parsed object; gateway logs show upstream latency + `provider_response.model=gemma2:27b` |
| **GW-04** | Schema-backed plan endpoint | Exercise `/plan` which performs retries + validation | **Terminal A:** gateway still running. **Terminal B:** POST sample profile to `http://localhost:8801/plan` (curl/Postman); verify validator artifacts | HTTP 200 with plan matching `dashboard_plan.schema.json`; metadata includes `round_trips <= 2` |
| **GW-05** | Unreachable Azure host | Confirm errors bubble up cleanly | Temporarily set `OLLAMA_HOST=https://invalid-host` and resend `/json`; capture logs | Gateway returns 502 with descriptive message, retried once; no crash |
| **GW-06** | Timeout handling | Ensure `OLLAMA_TIMEOUT_SECONDS` respected | **Terminal A:** gateway with `OLLAMA_TIMEOUT_SECONDS=5`. **Terminal B:** trigger `/json` calls while `tcproxy`/network rules throttle Azure | Request aborts at timeout, HTTP 504/502 returned, telemetry logs `elapsed_ms` |

### B. Agent Orchestrator ↔ Gateway Contract

| ID | Scenario | Objective | Steps | Expected |
| --- | --- | --- | --- | --- |
| **ORCH-01** | CLI handshake | Confirm CLI uses configured Ollama host | **Terminal A:** ensure your target Ollama endpoint is reachable. **Terminal B:** `cd app/agent-service/AgentOrchestrator`; set `ORCH_OLLAMA_HOST=https://planner-ignite-demo-evdeo...azurecontainerapps.io`; run `python -m agent_orchestrator.cli ..\CsvProfilerAgent\samples\retail_superstore_sample.csv` | CLI sends `/api/chat` request with schema + prompt metadata; logs show matching host |
| **ORCH-02** | Payload validation | Ensure orchestrator sends schema + prompt metadata | **Terminal A:** gateway in debug log mode. **Terminal B:** run CLI; inspect request body for `schema` + `plan_version` fields via gateway terminal output | Request includes schema reference, `prompt_version`, session id; orchestrator respects `planner_mode` |
| **ORCH-03** | Error propagation | Gateway returns invalid JSON; orchestrator should surface actionable error | **Terminal A:** run gateway against live Ollama via a chaos proxy (e.g., `toxiproxy`) that corrupts the response body while requests still reach ACA. **Terminal B:** run CLI and observe failure | CLI exits non-zero, prints validation error referencing schema path |
| **ORCH-04** | Retry + fallback | Verify orchestrator retries planner failure once, then surfaces fallback plan | **Terminal A:** run chaos proxy (`toxiproxy`) affecting gateway; **Terminal B:** run CLI; **Terminal C (optional):** tail orchestrator logs | Log shows retry with new prompt hash; workflow succeeds on 2nd attempt or surfaces fallback plan artifact |
| **ORCH-05** | API surface to frontend | If FastAPI wrapper enabled, `POST /upload` triggers orchestrator path | **Terminal A:** gateway; **Terminal B:** start API `python -m agent_orchestrator.api`; **Terminal C:** upload `samples/revenue.csv` (curl/Postman) and monitor gateway traffic | API returns session id + dashboard link; gateway receives plan request with same `session_id` |
| **ORCH-06** | Telemetry correlation | Ensure correlation IDs flow from orchestrator to gateway logs | Enable structured logging; run CLI; compare `session_id`/`prompt_hash` across orchestrator + gateway logs | IDs align, enabling trace stitching in App Insights |

### C. Additional Functional Coverage

| ID | Scenario | Objective | Steps | Expected |
| --- | --- | --- | --- | --- |
| **FUNC-01** | CSV profiler integration | Validate orchestrator either calls remote profiler or local module respecting row caps | Point `ORCH_CSV_PROFILER_ENDPOINT` at the staging profiler API (or leave unset for local module); run workflow | Profiler invoked once; respects `csv_profiler_max_rows`; profiler errors propagate nicely |
| **FUNC-02** | Plan-to-render pipeline | Ensure dashboard plan feeds renderer/prebuilt adapters | **Terminal A:** gateway; **Terminal B:** run orchestrator CLI with `--output-dir app/agent-service/AgentOrchestrator/artifacts`; inspect HTML/assets | Output contains rendered charts, stored under session-specific folder |
| **FUNC-03** | Storage tool hooks | Smoke-test `app/agent-service/storage_tool` reading/writing artifacts | **Terminal A:** run storage tool service/CLI session; **Terminal B:** invoke orchestrator output upload, passing responses back to Terminal A | Storage configs (connection string / Managed Identity) resolved; errors logged |
| **FUNC-04** | Frontend contract regression | Replay orchestrator API responses into the frontend contract harness | **Terminal A:** start harness `node frontend-service/mock/server.mjs`; **Terminal B:** feed orchestrator output via HTTP; **Terminal C (optional):** open browser hitting the harness endpoint | UI renders sample dashboard without schema mismatches |
| **FUNC-05** | Multi-dataset batch | Exercise repeatability across varied datasets | **Terminal A:** gateway; **Terminal B:** run orchestrator sequentially on Retail, CitiBike, Telco samples | Each run generates unique session id, `plan_version`, and chart mix; latency recorded |
| **FUNC-06** | CLI ergonomics | Validate CLI flags (`--skip-plan`, `--planner-mode remote`, etc.) behave | **Terminal A:** gateway against live Ollama. **Terminal B:** execute CLI with each flag combo | Flags map to expected behavior; help text accurate |

### D. Non-Functional, Security, and Observability

| ID | Scenario | Objective | Steps | Expected |
| --- | --- | --- | --- | --- |
| **NF-01** | Load / concurrency | Demonstrate gateway sustains ≥5 concurrent planner calls | **Terminal A:** gateway; **Terminal B:** run load tool (`locust`, `hey`); optional Terminal C for monitoring `kubectl logs` | 95th percentile latency < timeout; no shared-state corruption |
| **NF-02** | Cold-start readiness | Measure ACA cold-start and local gateway startup | Restart ACA container; trigger `/json`; record time to first byte | Time recorded, doc updated if >30s |
| **NF-03** | Logging hygiene | Ensure no sensitive CSV data logged | Review logs from full run; search for raw row data | Only summaries & metadata appear |
| **NF-04** | Config drift guard | Validate `.env` + `start_gateway.ps1` match infra values | Diff env files vs `infra/ollama.parameters.json`; run `pytest` config test | Alert when drift detected |
| **NF-05** | Security scanning | Ensure dependencies stay patched | Run `pip-audit` / `bandit` within gateway + orchestrator (same terminal is fine) | `pip-audit` exits clean or documented issues filed |
| **NF-06** | Remote outage handling | Understand orchestrator behavior when the live Ollama service is unreachable | **Terminal A:** keep gateway targeting ACA. **Terminal B:** block outbound access (firewall/offline), run CLI, and observe failure telemetry (no local fallback) | Workflow surfaces clear planner outage errors; no silent fallbacks |

## 8. Local Frontend + Agent E2E (Remote Ollama)

### 8.1 Objectives

- Validate that the React frontend and FastAPI agent can both run locally while planner traffic goes to the Azure-hosted Ollama deployment via the gateway.
- Catch regressions in upload UX, dashboard preview rendering, and agent HTTP contracts before shipping a new demo build.
- Ensure environment hints and `.env` samples accurately describe the mixed local/remote workflow.

### 8.2 Prerequisites

| Requirement | Notes |
| --- | --- |
| Node.js 20+, npm 10+ | For `app/frontend-service` dev server |
| Python 3.11 + virtualenv | For `app/agent-service/AgentOrchestrator` FastAPI app |
| Azure Ollama FQDN | e.g. `https://ollama-ignite-demo-evdeo...azurecontainerapps.io` |
| Planner gateway schema | `app/agent-service/OllamaStructuredJson/ChartJsonSpec.md` kept in sync |
| Local storage option | Either Azurite (`UseDevelopmentStorage=true;`) or real storage connection string |

Set the following environment variables before launch (sample for PowerShell):

```powershell
$env:OLLAMA_MODE='remote'
$env:OLLAMA_HOST='https://ollama-ignite-demo-evdeo...azurecontainerapps.io'
$env:PLAN_SCHEMA_PATH='schemas/dashboard_plan.schema.json'
$env:ORCH_OLLAMA_HOST='https://planner-ignite-demo-evdeo...azurecontainerapps.io'
$env:AZURE_STORAGE_CONNECTION_STRING='UseDevelopmentStorage=true;'
$env:VITE_AGENT_BASE_URL='http://localhost:8000'
```

### 8.3 Launch Sequence

1. **Terminal A – Gateway:** `cd app\agent-service\OllamaStructuredJson; python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt; uvicorn app.service:app --port 8801 --reload`. Confirm logs show `mode=remote` and the Azure host.
2. **Terminal B – Agent API:** `cd app\agent-service\AgentOrchestrator; python -m venv .venv; .venv\Scripts\activate; pip install -e .; uvicorn agent_orchestrator.api.app:app --port 8000 --reload`. Verify `/docs` loads locally.
3. **Terminal C – Frontend:** `cd app\frontend-service; npm install; npm run dev`. Ensure the dev server prints the local URL (default `http://localhost:5173`).
4. **Optional Terminal D – Azurite:** If you do not use the connection string, run `azurite --blobHost 0.0.0.0 --blobPort 10000` and update `AZURE_STORAGE_CONNECTION_STRING` with the Azurite hostname.
5. Record timestamps for each startup in the test log; these numbers help track cold-start regressions in future runs.

### 8.4 Local E2E Test Matrix

| ID | Scenario | Objective | Steps | Expected |
| --- | --- | --- | --- | --- |
| **FE-01** | Happy-path upload | Validate upload → profile → plan → render when all services are local except Ollama | In browser hit frontend dev URL; upload `samples/revenue.csv`; watch Network tab for `/upload`, `/dashboard/plan`, `/dashboard/view` | Upload returns 202/200; plan request hits gateway (Terminal A logs show remote call); dashboard renders in UI |
| **FE-02** | Planner outage surfacing | Ensure frontend surfaces planner errors while agent keeps responding | Stop Terminal A (gateway) after frontend upload starts; repeat upload | Agent returns 502/503 JSON with error message; frontend shows non-blocking error toast |
| **FE-03** | Large CSV guardrails | Confirm frontend enforces size guidance and agent sampling | Upload Citi Bike sample (~large rows); monitor agent logs for sampling notice | Frontend warning banner appears; agent logs `csv_profiler_max_rows` clamp |
| **FE-04** | Dashboard refresh | Validate that refreshing the dashboard page reuses cached artifacts | Complete FE-01, then refresh browser; ensure agent storage has existing artifact; no new planner call should appear in Terminal A | Gateway logs show zero new `/json` requests; frontend fetches `/dashboard/view?session=<id>` successfully |
| **FE-05** | Cross-origin checks | Verify CORS headers allow frontend ↔ agent calls | Inspect browser devtools for each API call; confirm `Access-Control-Allow-Origin` matches dev server | No CORS errors; retries not triggered |
| **FE-06** | Telemetry correlation | Ensure session IDs from frontend propagate to gateway logs | Capture session ID embedded in frontend response; search for same ID in agent + gateway logs | IDs match, enabling trace stitching |

Log pass/fail for each FE test alongside the existing GW/ORCH entries so regressions are traceable across the full stack.

## 9. Reporting & Sign-off

- Track execution status in `todo.md` or Azure Boards, referencing test IDs above.
- For every failure, record `TestID`, impacted component (gateway, orchestrator, storage, frontend harness, etc.), environment, and the exact command or HTTP request that triggered it so we can grep logs quickly.
- Log defects with repro details (dataset, env, gateway/orchestrator commit) and attach artifacts.
- Release sign-off requires all GW/ORCH/FUNC critical tests to pass, NF tests sampled within past sprint, and no Sev1 defects open.
