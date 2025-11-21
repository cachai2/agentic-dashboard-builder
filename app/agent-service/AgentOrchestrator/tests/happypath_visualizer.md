# Happy Path Visualizer

## Purpose

- Document how to take the profiler + planner artifacts from the happy path test and render the dashboard HTML via ChartRenderingAgent.
- Serves as the “part 2” after `tests/test_telco_happy_path.py` verifies planner output.

## Prerequisites

- `C:\Python313\python.exe` (or any Python 3.11+ interpreter with repo deps installed).
- Plotly renderer wired up by `DashboardRenderer` (automatic path bootstrap) and the `ChartRenderingAgent` dependencies installed (`pip install -e app/agent-service/ChartRenderingAgent`).
- Happy-path artifacts already generated (e.g., run the test in remote or mock mode to populate `artifacts/telco_churn/plan.json`).

## CLI

- Script: `tests/happypath_visualizer.py` (Typer CLI).
- Defaults:
  - Dataset: `app/agent-service/CsvProfilerAgent/samples/telco_churn_sample.csv`.
  - Plan JSON: `app/agent-service/AgentOrchestrator/artifacts/telco_churn/plan.json`.
  - Output HTML: `app/agent-service/AgentOrchestrator/artifacts/telco_churn/telco_dashboard.html`.

### Usage

```powershell
C:\Python313\python.exe app/agent-service/AgentOrchestrator/tests/happypath_visualizer.py \
    --dataset app/agent-service/CsvProfilerAgent/samples/telco_churn_sample.csv \
    --plan app/agent-service/AgentOrchestrator/artifacts/telco_churn/plan.json \
    --out app/agent-service/AgentOrchestrator/artifacts/telco_churn/telco_dashboard.html
```

- Omitting the options uses all defaults.
- On success, you’ll see: `Dashboard HTML written to ... with X rendered sections (skipped: Y).`

## What It Does

1. Loads the planner payload (already validated by the happy path test).
2. Instantiates `DashboardRenderer`, which now auto-imports ChartRenderingAgent modules.
3. Converts plan sections into ChartRendering payloads, writing inline datasets for funnel charts when needed.
4. Emits a full HTML dashboard plus metadata in the artifacts folder.

## Troubleshooting

- `ChartRenderingAgent package not available`: ensure the package path exists and dependencies are installed.
- `Dataset '<name>' not found in plan`: the renderer registers dataset aliases automatically, but older plan files may need regenerating.
- Skipped sections: indicates chart types not yet supported by ChartRenderingAgent. The HTML still renders remaining sections; enhance renderers to reduce skips.
