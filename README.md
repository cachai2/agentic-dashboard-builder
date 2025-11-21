# Ignite Demo: Automatic Dashboard Generation Platform

> **Status (Nov 2025)** – `azd up` provisions three Azure Container Apps (React frontend, FastAPI agent, Ollama GPU), shared Azure Files storage, Managed Identity, Application Insights, and Azure Container Registry. The GPU workload now pulls `gemma2:27b` during rollout, and the frontend ships as its own Container App.

- Latest tested services: `frontend`, `agent`, `ollama`
- Infra as code: `infra/main.bicep` orchestrated via `azd`
- Deployment workflow: `azd up` → `azd package <service>` → `azd deploy <service>` → `azd env refresh`

---

## Quick Start

### Prerequisites

- Azure CLI + [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- Node.js 20+ (frontend dev) and Python 3.11 (agent service dev)
- Docker (for local image builds) and access to an Azure subscription with ACA serverless GPU quota

### Bootstrap Environment

```powershell
azd auth login
azd env new ignite-demo
azd up
```

### Iterate on Individual Services

```powershell
# swap <service> for frontend | agent | ollama
azd package <service>
azd deploy <service>
azd env refresh
```

`azd env refresh` keeps `.azure/<env>/.env` aligned with the latest outputs (container app names, identities, storage accounts). Source this file locally when running services outside Azure.

---

## Architecture Overview

```text
[ React Frontend (ACA) ]
    |
    | Upload CSV / generate dashboard
    v
[ FastAPI Agent Service (ACA CPU profile) ]
    - /upload (CSV ingest + pandas cache)
    - /dashboard/plan (calls GPU planner)
    - /dashboard/view (Plotly render)
        |
        | Structured JSON plan request
        v
[ Ollama GPU Planner (ACA GPU profile) ]
    - /healthz, /api/generate style endpoints
    - Init container pulls gemma2:27b into Azure Files volume

[ Shared Resources ]
  - Azure Files (Ollama model cache + agent artifacts share)
  - Azure Storage + ACR + Application Insights
  - User-assigned Managed Identity (registry + storage auth)
```

Frontend calls the public ingress for the agent service; the agent reaches the GPU container via ACA internal DNS (`https://ollama-<env>...internal...`).

---

## Repository Layout

| Path | Description |
|------|-------------|
| `app/` | FastAPI agent (upload/profile/plan/render) + shared schemas/prompt assets |
| `app/frontend-service/` | React + Vite SPA for upload + dashboard visualization |
| `app/ollama-service/` | Minimal Docker context for the ACA Ollama container |
| `app/agent-service/` | Agent Orchestrator, shared agents (CsvProfiler, ChartRendering, structured JSON playground), and the Docker context for the CPU service |
| `infra/` | Bicep modules composed by `infra/main.bicep` |
| `Playground/OllamaStructuredJson/` | Standalone FastAPI service used to test structured JSON prompts |
| `docs/`, `General Architecture.md`, `More Specific Architecture.md` | Deep-dive design notes and schemas |

---

## Service Snapshot

| Service | Tech Stack | Purpose | Key Env Vars |
|---------|------------|---------|--------------|
| `frontend` | React + Vite + Plotly | Upload CSVs, call `/dashboard/*`, render HTML | `VITE_AGENT_BASE_URL` (set by azd) |
| `agent` | Python 3.11 + FastAPI | Profiling, planner orchestration, Plotly renderer | `OLLAMA_HOST`, `OLLAMA_MODEL`, `PLAN_SCHEMA_PATH` |
| `ollama` | `ollama/ollama` base + init container | Hosts gemma2:27b on ACA GPU profile | `OLLAMA_CONTEXT_LENGTH`, Azure Files secrets |
| `nginx-auth-proxy` (optional) | NGINX | Legacy ingress proxy retained for fallback | TLS/Basic Auth secrets |

`azure.yaml` wires each service to its Dockerfile/context so `azd package` can build/push consistently.

---

## DashboardPlan Contract (Excerpt)

Planner responses must satisfy `schemas/dashboard_plan.schema.json`.

```json
{
  "title": "Quarterly Revenue Overview",
  "priority": "overview",
  "sections": [
    {
      "title": "Trends",
      "charts": [
        {
          "id": "rev_timeseries",
          "type": "line",
          "query": {
            "operation": "timeseries_agg",
            "x": "order_date",
            "y": "revenue",
            "agg": "sum",
            "time_grain": "month"
          },
          "insight": "Revenue is trending upward post-Q2."
        }
      ]
    }
  ]
}
```

Guardrails:

- Stay within the profiled schema (no invented columns).
- CPU service validates every plan with `jsonschema`; on failure it retries once then falls back to a minimal plan.
- Future work will drop only invalid charts instead of the entire plan.

---

## Local Development Workflows

### Agent CPU Service (`/app`)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

- Upload CSVs: `POST http://localhost:8000/upload`
- Point to the remote GPU: set `OLLAMA_HOST` and `OLLAMA_MODEL=gemma2:27b`

### Agent Service (Docker image)

```powershell
# build the image from the repo root
docker build -t agent-service:dev app/agent-service

# run the planner gateway locally (see Playground/OllamaStructuredJson)
cd app\agent-service\OllamaStructuredJson
$env:OLLAMA_MODE='remote'
$env:OLLAMA_HOST='https://ollama-<env>...azurecontainerapps.io'
uvicorn app.service:app --port 8801 --reload

# in another terminal, launch the agent container
docker run --rm -it ^
  -p 8080:8080 ^
  -e ORCH_PLANNER_GATEWAY_HOST="http://host.docker.internal:8801" ^
  -e OLLAMA_MODEL="gemma2:27b" ^
  -e AZURE_STORAGE_CONNECTION_STRING="UseDevelopmentStorage=true;" ^
  agent-service:dev
```

- The container entrypoint (`docker-entrypoint.sh`) automatically starts `uvicorn agent_orchestrator.api.app:app --host 0.0.0.0 --port 8080`. Override it by passing your own command (`docker run ... bash`) or by setting `APP_MODULE`, `HOST`, or `PORT` environment variables.
- When you prefer to keep storage traffic inside Docker, run Azurite on a shared network and update the connection string with the container hostname (e.g. `BlobEndpoint=http://azurite:10000/devstoreaccount1`). Otherwise `UseDevelopmentStorage=true;` targets a host-running Azurite instance.
- Planner traffic is routed through `ORCH_PLANNER_GATEWAY_HOST`; use `host.docker.internal` when the gateway runs on your workstation, or switch to the container name when both run on the same Docker network.

### Frontend (`app/frontend-service`)

```powershell
npm install
npm run dev
```

Expose `VITE_AGENT_BASE_URL=http://localhost:8000` when pairing with the locally running FastAPI service.

### Structured JSON Playground (`Playground/OllamaStructuredJson`)

```powershell
cd Playground/OllamaStructuredJson
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:OLLAMA_MODE='remote'
$env:OLLAMA_HOST='https://ollama-<env>...azurecontainerapps.io'
$env:OLLAMA_MODEL='gemma2:27b'
uvicorn app.service:app --port 11434 --reload
```

### ACA Ollama Container (`app/ollama-service`)

- Dockerfile stays close to upstream `ollama/ollama` and exposes port `11434`.
- Model layers are pre-pulled in the ACA init container:

  ```bicep
  args: ['pull', 'gemma2:27b']
  ```

- Azure Files (`ollamaModelStorageName`) keeps the model cache between revisions.

---

## Deploying with `azd`

1. **Provision / Update Infra**

   ```powershell
   azd up
   ```

   Creates/updates the ACA environment, workload profiles, storage, identities, Insights, and registry.

2. **Package + Deploy a Service**

   ```powershell
   azd package agent
   azd deploy agent
   ```

   Use `--from-package` if you already built a tarball locally.

3. **Refresh Environment Outputs**

   ```powershell
   azd env refresh
   ```

4. **Smoke Test**

   - Frontend endpoint: printed after deploy or via `azd monitor --app frontend`
   - GPU health: `Invoke-RestMethod https://ollama-<env>.../healthz`

Tips: rerun `azd provision` only when `infra/` changes, and prefer `azd down` for full teardown after the event.

---

## Model & Data Handling

- **Default model**: `gemma2:27b` everywhere (init container + application defaults + playground docs).
- **Context tuning**: `OLLAMA_CONTEXT_LENGTH=32768`, `OLLAMA_KEEP_ALIVE=15m` to keep JSON prompts responsive.
- **Inputs**: Profiling metadata (dtype, null %, cardinality, basic correlations) grounds each plan request.
- **Dataset guardrails**: ≤100k rows for full profiling, sample larger files to 50k rows, top-k for high-cardinality categorical fields.
- **Storage**: CSVs and model weights live in Azure Files; CPU sessions stay in-memory per replica today.

---

## Observability & Operations

| Signal | Source | Notes |
|--------|--------|-------|
| `plan_latency_ms`, `upload_to_first_byte_ms` | App Insights custom events | Emitted by FastAPI service |
| Revision timestamps | ACA portal / `az containerapp revision list` | Revisions update only when specs change |
| GPU readiness | `/healthz` + ACA metrics | Expect cold-start latency when scaling from zero |
| Storage mounts | ACA diagnostics | Init container logs show Azure Files failures |

For deeper debugging, run `az containerapp logs show --name <service> --follow` plus `azd monitor`.

---

## Additional References

- `General Architecture.md` – high-level narrative and demo script
- `More Specific Architecture.md` – DashboardPlan schema + flow details
- `Working with JSON.md` – validation guidelines and retry strategy
- `docs/` – supplementary diagrams, FAQs, and notes

If you add new services or change Azure resources, update this README plus `azure.yaml` and the relevant Bicep modules before running `azd provision`.
