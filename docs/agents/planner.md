# Planning Agent (GPU Service)

## Workspace Setup

- Work from the repo root so `schemas/`, `infra/`, `prompts/`, and planner service code remain accessible to Copilot.
- Key paths: `app/planner.py`, forthcoming `planner_service/`, `Dockerfile.gpu`, `docs/agents/planner.md`.
- Keep a terminal anchored at root for `uvicorn`, container builds, and `azd` deploy commands.

## 1. Scope & Responsibilities

- Generates `DashboardPlan` JSON given `profile_summary`, user hints, and system prompts.
- Runs on Azure Container Apps GPU workload profile (serverless GPU) or Azure AI endpoint.
- Enforces schema compliance, returning only supported operations/chart types.
- Emits prompt/response metadata for auditing and prompt versioning.

## 2. Contracts

| Component | Contract |
|-----------|----------|
| API | `POST /plan_dashboard` (preferred) or OpenAI-style `/chat/completions`. Request body includes `session_id`, `profile_summary`, optional `user_goal`. |
| Output | JSON conforming to `schemas/dashboard_plan.schema.json`. Include `plan_version`, `prompt_version`, `generated_at`. |
| Error Handling | On malformed JSON, respond with 400 and diagnostic; orchestrator may retry once. |
| Security | Accept only structured metadata; ignore untrusted free-form text fields to mitigate prompt injection. |

## 3. Dependencies & Configuration

- Prompt templates stored in `prompts/` (to be added) with semantic version tag.
- GPU container image (see `Dockerfile.gpu`) plus model weights or Azure AI credentials pulled via Managed Identity/Key Vault.
- Observability via Application Insights + ACA metrics (GPU utilization, cold start time).

## 4. Run Workflow (Local)

1. Start planner FastAPI app (mock version currently in `app/planner.py`).
2. Send payload from orchestrator or `scripts/test_planner.py` (future) and verify JSON validity.
3. Update prompt/system message; bump `prompt_version` and document change log in this file.

## 5. Observability & Guardrails

- Log `prompt_hash`, `profile_signature`, `charts_count`, `model_latency_ms`.
- Reject requests exceeding predefined size; return descriptive error.
- Keep prompt + response truncation logic to prevent excessive logging of data.
- Use Managed Identity for storage access (if reading data for few-shot context) instead of embedding secrets.

## 6. Open Threads / TODOs

- Stand up actual GPU planner service with health probes and readiness check.
- Implement caching: identical `profile_signature` should reuse previous plan when TTL permits.
- Add guardrail layer (semantic validator) for chart count, type balance, and KPI coverage.
- Persist prompt/plan pairs for audit and model evaluation.
