# Microsoft Agent Framework Integration

This folder packages the CSV profiler as a reusable Microsoft Agent Framework tool.

## Files

- `tool.profile_csv.yaml` – manifest that describes the HTTP action (method, path, query parameters,
  and response schema). Point the Agent Framework CLI or portal at this file when you register the tool.

## Usage

1. **Run the profiler service**

   ```powershell
   uvicorn app.main:app --port 8101 --reload
   ```

2. **Export the base URL** so the manifest resolves correctly:

   ```powershell
   $env:CSV_PROFILER_BASE_URL = "http://localhost:8101"
   ```

3. **Register the tool** inside Microsoft Agent Framework (CLI example):

   ```powershell
   maf tools register --manifest agentframework/tool.profile_csv.yaml
   ```

   Replace `maf` with whatever entry point your Agent Framework installation provides. The command simply
   uploads the manifest, so the agent can call `POST /profile` with raw CSV data.

Once registered, agents invoke the `profile_csv` action by providing CSV bytes (or base64-decoded data) and optional
`dataset_name` / `max_rows` query parameters. The response matches `schemas/dashboard_plan.schema.json`, so any planner
inside the framework can rely on the established contract.
