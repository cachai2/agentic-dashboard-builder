# Happy Path Test Notes

## Overview

- Test file: `tests/test_telco_happy_path.py`.
- Purpose: prove the end-to-end profiler → planner workflow works deterministically for the `telco_churn_sample.csv` dataset.
- Scope: validates profiling JSON, planner payload, workflow events, and metadata. Rendering is intentionally out of scope for this test.

## Workflow Behavior

1. `UploadToDashboardWorkflow` receives the telco CSV.
2. `_profile_executor` calls `profile_dataset`, ensuring the profiler tool produces row/column counts, KPI annotations, funnel hints, etc.
3. `_planner_executor` calls `generate_dashboard_plan` unless `skip_planner=True`.
4. The workflow emits a `WorkflowOutputEvent` containing `{ profile, plan }`.
5. Assertions verify:
   - Both executors ran (by scanning workflow events).
   - Profile metadata matches expectations (dataset name, sampled rows, column count).
   - Planner metadata references the supplied session ID and prompt version.
   - KPI, retention funnel, and loyalty scatter sections in the plan align with profiler annotations.

## Default (Mock) Mode

- `tests/conftest.py` sets `ORCH_PLANNER_MODE=mock` unless the env var is already defined.
- Running `python -m pytest tests/test_telco_happy_path.py` keeps everything local and finishes in ~3-4 seconds.
- Useful for CI because no external network calls are made.

## Remote Ollama Mode

- Export env vars before pytest:

  ```powershell
  $env:ORCH_PLANNER_MODE = 'remote'
  $env:ORCH_OLLAMA_HOST = 'https://planner-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io'
  C:\Python313\python.exe -m pytest tests/test_telco_happy_path.py -vv
  ```

- With remote mode, the planner step hits the ACA Ollama deployment directly. Latest run: `1 passed in ~241s` (latency dominated by LLM inference).
- The same assertions run; failures usually indicate schema validation issues or gateway outages.

## Why Rendering Is Not Included Yet

- Plotly/ChartRendering dependencies aren’t always available in the orchestrator venv (currently missing `ChartRenderingAgent` package wiring).
- Rendering requires local Plotly + kaleido tooling and larger artifacts, which slows CI.
- Once the renderer modules are installable, we can create a follow-up test that calls `DashboardRenderer` and verifies HTML output.

## Troubleshooting

- If the test hangs in remote mode, confirm the Ollama host is reachable and `ORCH_OLLAMA_HOST` points to the deployed model.
- Schema validation failures appear as `jsonschema.ValidationError`, printed in pytest output. Check `artifacts/planner_payloads` for the offending request/response pairs.
- Profiling failures usually mean the CSV path moved; the test asserts `telco_churn_sample.csv` exists under `app/agent-service/CsvProfilerAgent/samples/`.
