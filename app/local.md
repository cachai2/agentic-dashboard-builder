# Local end-to-end test (remote Ollama)

Use these steps to run both services on your dev machine while the orchestrator calls the hosted Ollama deployment directly.

## Quick start script

If you just want everything booted automatically, run the helper script from the repo root:

```powershell
pwsh .\scripts\start-local-stack.ps1
```

Flags:

| Flag | Description |
| --- | --- |
| `-OllamaHost <url>` | Override the remote Ollama host (defaults to the Azure instance). |
| `-AgentPort <port>` | Change the FastAPI port (default `8800`). |
| `-FrontendOrigin <origin>` | Origin added to `ORCH_ALLOWED_ORIGINS` (default `http://localhost:5173`). |
| `-SkipInstalls` | Skip `pip install -e . --pre` and `npm install` if you already ran them. |

The script:

1. Ensures the orchestrator virtual env exists and installs deps (unless `-SkipInstalls`).
2. Writes `agent-service/AgentOrchestrator/.env` pointing at the remote Ollama host and allowing your local frontend origin.
3. Writes `frontend-service/.env.local` targeting `http://localhost:<AgentPort>` with `VITE_USE_MOCK=false`.
4. Launches two new PowerShell windows running `uvicorn … --reload` and `npm run dev`.

Close each spawned terminal (Ctrl+C) to stop the services.

## Manual steps

## Prerequisites

- Python 3.10+ with `venv`
- Node.js 18+
- Access to the remote endpoints:
  - Ollama host: `https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io`
  - FastAPI orchestrator will run locally on `http://localhost:8800`

## 1. Start the Agent Orchestrator locally

```powershell
cd agent-service/AgentOrchestrator
python -m venv .venv
.\.venv\Scripts\activate
pip install -e . --pre
```

Configure the orchestrator to call the remote Ollama host and to accept browser calls from the local frontend:

```powershell
# PowerShell examples – create/update .env in this folder
Set-Content -Path .env -Value @'
ORCH_OLLAMA_HOST="https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io"
ORCH_PLANNER_MODE="remote"
ORCH_ALLOWED_ORIGINS="http://localhost:5173"
'@
```

> Keep any existing planner settings you need (model name, timeouts, storage paths, etc.).

Run the API:

```powershell
uvicorn agent_orchestrator.api.app:app --host 0.0.0.0 --port 8800 --reload
```

Sanity check from a separate terminal:

```powershell
Invoke-WebRequest http://localhost:8800/dashboard/status?sessionId=test
```

A `404 Session not found` response confirms the server is reachable.

## 2. Start the frontend against the local API

```powershell
cd frontend-service
npm install
Copy-Item .env.local.example .env.local -Force
```

Ensure `.env.local` contains:

```env
VITE_API_BASE_URL=http://localhost:8800
VITE_USE_MOCK=false
```

Then run the dev server:

```powershell
npm run dev
```

Visit `http://localhost:5173` and confirm the badge shows **Live planner (API)**.

## 3. Exercise the flow

1. Upload a CSV via the playground.
2. Watch the status timeline poll `http://localhost:8800/dashboard/status`.
3. Confirm the orchestrator log shows requests headed to the remote Ollama host.

## Troubleshooting

- `net::ERR_CONNECTION_REFUSED` – ensure the FastAPI server is running on port 8800 and that `VITE_API_BASE_URL` points to it.
- CORS errors – verify `ORCH_ALLOWED_ORIGINS` includes `http://localhost:5173`. Restart `uvicorn` after changing the env file.
- Planner errors – double-check `ORCH_OLLAMA_HOST` (and model/timeouts) plus any credentials required by the remote Ollama service.

Once both services run locally, you can iterate quickly while still exercising the real planner hosted in Azure.
