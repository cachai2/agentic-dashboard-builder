Rendering + adapters: The orchestrator README in README.md still lists the biggest gap as wiring the Chart Rendering agent and Prebuilt adapters so each workflow run emits actual Plotly HTML (first item under “Next actions”). Until that’s done the agent can’t hand the frontend a real dashboard artifact.

Agent Framework graph: Same README calls out registering the profiler/planner/renderer tools with a PersistentAgentsClient and exposing a deterministic workflow. That means defining the Pydantic contracts, hooking each tool in, and adding retries/validation paths around the remote Ollama planner.

[done] Storage + persistence: upload-orchestrator.md explicitly leaves storage as “future” plus the new storage-tool-reference.md documents the Blob helper we expect to reuse. We still need to instantiate that tool in the FastAPI service, persist uploads/results, and publish signed URLs back to the frontend.

[done] Provision + surface env vars: Re-run azd up and azd env refresh so AGENT_STORAGE_ACCOUNT_NAME/AGENT_STORAGE_CONTAINER_NAME land in .azure/<env>/.env, then propagate them into the agent Container App (either via azure.yaml env overrides or the Bicep template). Until that happens the helper will raise the “not configured” runtime error in storage_tool/config.py.

Instantiate the helper in FastAPI: Update main.py (or a new startup module) to call get_storage_settings(), build an ArtifactStorage, and hang a CsvStorageTool off app.state. No other services use it yet, so wiring can stay local to this CPU app.

Persist uploads/results: Replace the in-memory SESSIONS payload with something that writes the raw CSV to Blob (via upload_dataset) and stores the plan/results metadata (upload_results, upload_dashboard). Minimum change: capture the blob paths in session state while maintaining current behavior, then add endpoints to fetch signed URLs for the frontend when the other agent is ready.

Managed identity permissions: The infra template already assigns Storage Blob Data Contributor to the user-assigned identity, but confirm the agent container uses that identity (in resources.bicep it does) and that the app uses DefaultAzureCredential without a connection string in production.

Configuration & fallbacks: Decide whether local development should use connection strings (set AZURE_STORAGE_CONNECTION_STRING) or Azurite. Document these expectations in storage-tool-reference.md and upload-orchestrator.md.

Tests & monitoring: Add at least a small storage smoke test (e.g., pytest that mocks BlobServiceClient) plus basic logging/metrics around upload/download failures so Application Insights can catch issues once the tool is live.





Reliability guardrails: Open items in upload-orchestrator.md cover planner retry/backoff and documenting the sampling/size limits once they’re enforced. Additionally, README.md notes the plan validator should eventually drop only invalid charts instead of discarding the entire plan—worth tracking as you keep hardening the planner.

Observability: Both the orchestrator README and the upload agent guide mention Application Insights/OpenTelemetry hooks. Nothing in the repo wires those up yet, so adding trace/log/metric emission (especially around /upload and planner latency) is still ahead.

Documentation/tests: The Agent Orchestrator README asks for sequence diagrams and troubleshooting notes once components solidify, and docs under docs/agents/*.md still have TODOs around automated tests for profiling/rendering. As you finish each capability, backfill those sections so future contributors know the happy path.