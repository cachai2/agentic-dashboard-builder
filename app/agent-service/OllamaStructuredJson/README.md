# Ollama Structured JSON Agent Playground

## Objective

Isolate the GPU-side logic responsible for calling Ollama (or a drop-in SLM) and guaranteeing valid `DashboardPlan` JSON responses. This agent should accept profiling summaries, craft prompts, call the local Ollama server, and enforce schema compliance before handing results to the orchestrator.

## Deliverables

1. Configurable prompt builder (`prompts/system.txt`, `prompts/user_template.txt`) with version tags and inline rationale.
2. Client wrapper around `ollama run` or the HTTP API, including timeout + cancellation support.
3. JSON validation layer that retries once with an automatic "fix invalid JSON" instruction and surfaces structured errors when validation fails.
4. Load test script (Locust or simple asyncio tool) proving the agent can serve at least 5 concurrent requests without corrupting state.
5. Telemetry/log statements capturing prompt hash, response token count, retry count, and elapsed milliseconds.

## Suggested Layout

```text
Playground/OllamaStructuredJson/
├─ app/
│  ├─ builder.py
│  ├─ client.py
│  ├─ validator.py
│  └─ service.py
├─ prompts/
│  ├─ system_v1.md
│  └─ user_template.md
├─ tests/
│  └─ test_schema_validation.py
└─ requirements.txt
```

## Integration Guidance

- Keep the HTTP surface compatible with the future ACA GPU container: `POST /plan` accepting `{ profile_summary, prompt_version }` and returning `{ plan, metadata }`.
- When adding new chart operations or metadata fields, update `schemas/dashboard_plan.schema.json` and ping the Rendering + Frontend agents.
- Store large model artifacts outside the repo (use Azure Files or Blob). For local dev, document how to run `ollama pull gpt-oss:20b` in this folder.
- Use environment variables (`OLLAMA_HOST`, `OLLAMA_MODEL`, `PLAN_SCHEMA_PATH`) instead of hardcoded values so azd can inject settings later.
- Structured-output toggles: `OLLAMA_SEND_JSON_SCHEMA=true` (default) enables sending the DashboardPlan schema in the `format` payload, while `OLLAMA_FORCE_JSON_MODE=true` keeps JSON-mode fallback when schema transmission is disabled.

## Stretch Goals

- Implement function-calling or JSON-schema mode once Ollama supports it, reducing retry logic.
- Add safety filters that sanitize column names or user comments before prompt injection.
- Emit OpenTelemetry traces so the Agent Framework orchestrator can correlate planner spans with CPU-side activity.

## Local Testing (GPU-Free Workflow)

Even though this agent ultimately targets a GPU-backed ACA container, you can still exercise most logic locally by mocking the Ollama endpoint and piping requests to a remote GPU when available.

1. Install dependencies and run unit tests:

   ```powershell
   cd Playground/OllamaStructuredJson
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   pytest
   ```

2. Start the planner service in mock mode on port `11434` so the CPU agent can call it without a GPU:

   ```powershell
   OLLAMA_MODE=mock uvicorn app.service:app --port 11434 --reload
   ```

3. To hit a real GPU-hosted Ollama instance (e.g., the ACA deployment), point the client at the remote host while keeping the local validator code:

   ```powershell
   $env:OLLAMA_HOST="https://<gpu-app-fqdn>"
   $env:OLLAMA_MODEL="gpt-oss:20b"
   python -m app.client --profile samples/profile.json
   ```

4. Capture JSON responses in `artifacts/` and run the validator offline to confirm schema compliance before promoting prompts:

   ```powershell
   python -m app.validator artifacts/latest_plan.json
   ```

Once the ACA GPU app is healthy, switch `OLLAMA_MODE=remote` and redeploy the same service container; no code changes are needed beyond the environment variables above.
