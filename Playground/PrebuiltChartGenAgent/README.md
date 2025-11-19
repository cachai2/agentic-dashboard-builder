# Prebuilt Chart Generation Agent Playground

## Objective

Spike on off-the-shelf chart builders (AutoViz, Deepchecks Visualization, Plotly Express templates, Evidently AI dashboards, etc.) to determine whether we can accelerate rendering versus hand-coding every chart. This sandbox lets copilots wire these tools to our `DashboardPlan` schema, capture pros/cons, and compare performance/UX against the bespoke renderer.

## Deliverables

1. Adapter layer that converts a `DashboardPlan` section into the input format expected by the chosen chart library.
2. Command or notebook that runs the builder with sample plan data and exports HTML/PNG assets to `artifacts/`.
3. Comparison log (`reports/comparison.md`) summarizing fidelity, load time, bundle size, and licensing considerations for each library tested.
4. Automated test (even a smoke script) that ensures the adapter doesn’t regress when the plan schema changes.
5. Recommendation checklist capturing when to prefer prebuilt output vs custom Plotly renderers.

## Current Sandbox Status

- Folder skeleton, sample plan (`tests/data/sample_plan.json`), and experiment notebooks now exist so copilots have a consistent starting point.
- `plotly_express` adapter is implemented end-to-end (HTML/PNG output) and covered by `tests/test_plotly_adapter.py`.
- `autoviz` and `deepchecks` adapters now emit HTML artifacts. Install the optional extras (`pip install -r requirements.adapters-extra.txt`) before using them. AutoViz uses the depVar hint (if any) while Deepchecks lets sections pick a suite via `"suite": "data_integrity|model_evaluation|train_test_validation"`.
- `reports/comparison.md` includes placeholders for fidelity/performance/licensing data—capture findings there after each run.
- `app/combine_artifacts.py` can stitch every HTML artifact into a single gallery (`artifacts/all_charts.html`) for quick sharing.

## Sample Dashboard Plans

- `tests/data/sample_plan.json` – Sales dashboard with revenue and pipeline velocity.
- `tests/data/marketing_attribution_plan.json` – Multi-section marketing metrics (ROI, spend vs leads, lead velocity).
- `tests/data/product_health_plan.json` – Product usage, latency, and retention cohorts for reliability/UX tracking.

## Suggested Layout

```text
Playground/PrebuiltChartGenAgent/
├─ adapters/
│  ├─ autoviz_adapter.py
│  ├─ deepchecks_adapter.py
│  └─ plotly_express_adapter.py
├─ experiments/
│  ├─ autoviz_demo.ipynb
│  └─ deepchecks_demo.ipynb
├─ artifacts/
├─ reports/
│  └─ comparison.md
├─ app/
│  └─ runner.py
└─ requirements.txt
```

## Integration Guidance

- Treat this agent as exploratory; keep dependencies isolated so we don’t inflate the main app’s footprint unless we adopt a library.
- Whenever a builder outputs HTML with inline scripts, sanitize/strip sensitive sections before checking into git (or store large outputs in `artifacts/.gitignore`).
- If a builder can only operate directly on pandas DataFrames, create mock DataFrame generators that match our profiling summaries so the adapter remains deterministic.
- Capture license usage (MIT, Apache, commercial) in `reports/comparison.md`—we’ll need that data before adopting any dependency.

## Local Testing

1. Install dependencies:

   ```powershell
   cd Playground/PrebuiltChartGenAgent
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Install optional adapter dependencies when you need AutoViz or Deepchecks:

   ```powershell
   pip install -r requirements.adapters-extra.txt
   ```

2. Run an experiment (example Plotly Express path):

   ```powershell
   python -m app.runner --plan tests/data/sample_plan.json --adapter plotly_express --out artifacts/plotly_sample.html
   ```

3. Try the AutoViz or Deepchecks adapters (HTML outputs only, requires optional deps):

   ```powershell
   python -m app.runner --plan tests/data/sample_plan.json --adapter autoviz --out artifacts/autoviz_sample.html
   python -m app.runner --plan tests/data/sample_plan.json --adapter deepchecks --out artifacts/deepchecks_report.html
   ```

4. Run the smoke tests to guard against schema drift:

   ```powershell
   python -m unittest tests.test_plotly_adapter tests.test_autoviz_adapter tests.test_deepchecks_adapter
   ```

5. Consolidate all generated HTML into a single gallery page when you want a sharable index:

   ```powershell
   python -m app.combine_artifacts --artifacts-dir artifacts --output artifacts/all_charts.html --title "Prebuilt Chart Gallery"
   ```

6. Open the artifact in a browser or launch a local static server on port `8110` for quick previews (the gallery page references the individual HTML files via `<iframe>`).

7. Update `reports/comparison.md` with your findings and link the artifact so others can inspect results asynchronously.

## Stretch Goals

- Automate A/B comparisons between bespoke and prebuilt outputs (pixel-diff or DOM-diff) to quantify fidelity gaps.
- Benchmark render time and bundle size for each library using the same plan inputs.
- Evaluate cloud-hosted chart services (e.g., Observable Plot, Power BI Embedded playground) if licensing allows, noting any networking/security implications.
