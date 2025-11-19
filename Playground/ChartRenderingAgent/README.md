# Chart Rendering Agent Playground

## Objective

Build and validate the Plotly/HTML rendering layer independently from the rest of the stack. Given a canonical `DashboardPlan` JSON (see `schemas/dashboard_plan.schema.json`), this agent should output a complete HTML snippet (or static image bundle) that the frontend can embed without extra logic.

## Deliverables

1. Parser that converts `DashboardPlan` sections into an internal representation (e.g., dataclasses or pydantic models).
2. Renderer registry (`renderers/<chart_type>.py`) that maps plan operations (timeseries, groupby, distribution, outliers, KPI) to Plotly figures.
3. Layout composer producing a responsive HTML document with per-section headings and anchor links.
4. Visual regression tests (e.g., `pytest + pytest-regressions` or HTML snapshot comparisons) covering at least one example per chart type.
5. CLI harness (`python -m render --plan samples/plan.json --out build/plan.html`) for easy manual review.

## Suggested Layout

```text
Playground/ChartRenderingAgent/
├─ renderers/
│  ├─ __init__.py
│  ├─ base.py
│  ├─ timeseries.py
│  ├─ groupby.py
│  └─ distribution.py
├─ app/
│  ├─ composer.py
│  ├─ registry.py
│  └─ cli.py
├─ tests/
│  ├─ data/
│  │  └─ sample_plan.json
│  └─ test_render_snapshots.py
└─ requirements.txt
```

## Chart Catalogue Plan

| Chart Family | Planner Ops | Visual DNA | Layout + UX Notes |
| --- | --- | --- | --- |
| **Timeseries Line/Area** | `timeseries`, `forecast` | Multi-line plot with optional forecast band; can collapse to single KPI sparkline | Pin shared time axis at bottom, show hover-on-demand legend, default palette = blue/purple ramp |
| **Comparative Bars** | `groupby`, `rank` | Vertical bars for up to 8 categories, auto-switch to horizontal if labels long | Include inline percent deltas next to bars, add reference line for overall mean when available |
| **Stacked Composition** | `composition`, `share_of_voice` | Stacked area (time) or stacked bar (single period); highlight top segment | Toggle between absolute and % stacking via toolbar chip |
| **Distribution Insight** | `distribution`, `histogram`, `boxplot` | Histogram with density overlay, switchable to boxplot for compact view | Surface mean/median markers; show outlier count pill in title |
| **Anomaly & Outlier** | `outliers`, `quality_gate` | Scatter/line hybrid with highlighted points and annotation cards | Pin annotations in right gutter so chart stays clean; support drill link payloads |
| **KPI Scorecards** | `kpi`, `headline` | Grid of tiles with big number, trend sparkline, badge for status | Auto-fit 3 cards per row on desktop, degrade to horizontal swipe on mobile embed |

### Sample Planner Payloads

```json
{"operation":"timeseries","x":"date","y":["revenue","target"],"options":{"forecast":{"upper":"yhat_upper","lower":"yhat_lower"}}}
```

```json
{"operation":"groupby","dimension":"region","metric":"revenue","options":{"sort":"desc","limit":6}}
```

```json
{"operation":"composition","x":"month","stacks":["product_a","product_b","services"],"options":{"normalize":true}}
```

```json
{"operation":"distribution","metric":"latency_ms","options":{"bins":30,"comparison":"prev_period"}}
```

```json
{"operation":"outliers","x":"timestamp","y":"error_rate","options":{"threshold":0.08}}
```

```json
{"operation":"kpi","title":"Net Revenue","value":1280000,"delta":{"value":0.12,"direction":"up"}}
```

### Low-Fidelity Layout Sketches

```text
Timeseries (dual line + forecast)
   Title: Revenue vs Target
   [──────────────  shared legend  ──────────────]
   | revenue  /\      forecast band
   |        /  \___
   |___target______\____________________________ time →

Comparative Bars (horizontal)
   Title: Revenue by Region
   West   ████████████████  $4.2M  (+12%)
   East   ████████████      $3.1M  (+4%)
   South  █████████         $2.6M  (−3%)

KPI Tiles
   ┌────────────┬────────────┬────────────┐
   │Revenue     │NPS         │Churn       │
   │$1.28M ↑12% │52  →       │3.1% ↓0.4pp │
   │sparkline   │sparkline   │sparkline   │
   └────────────┴────────────┴────────────┘
```

### Implementation Notes

- Start with the six families above; each maps cleanly to a renderer module and can be expanded with style variants.
- Treat layout sketches as acceptance criteria for spacing, labels, and metadata placement; revisit them once we have first Plotly renders.
- The sample plan snippets double as contract tests—drop them into `tests/data/` to bootstrap regression fixtures.

## Timeseries Renderer Blueprint

### Goals & Scenarios

- Render up to three simultaneous metrics on a shared time axis with optional secondary axis for rates/percentages.
- Provide context mode switching: `actuals` (raw), `trend` (rolling average), `forecast` (actuals + predictive band), and `comparison` (current vs prior period offset).
- Allow the orchestrator to compose KPI sparkline snippets by reusing the same renderer with `compact=true`.

### Planner Contract (JSON excerpt)

```json
{
   "operation": "timeseries",
   "title": "Revenue vs Target",
   "x": {"column": "date", "grain": "day"},
   "series": [
      {"id": "actual", "column": "revenue", "label": "Revenue", "axis": "primary"},
      {"id": "target", "column": "target", "label": "Target", "style": {"dash": "dot"}}
   ],
   "forecast": {"lower": "yhat_lower", "upper": "yhat_upper", "label": "Forecast"},
   "comparison": {"mode": "previous_period", "offset_days": 30},
   "events": [
      {"ts": "2024-09-15", "label": "Launch", "annotation": "APAC promo"}
   ],
   "options": {
      "compact": false,
      "y_axis_format": "currency",
      "rolling_window": 7
   }
}
```

### Visual & UX DNA

- **Legend** floats inside the plot area (top-left) and collapses into a pill stack on narrow widths.
- **Forecast band** uses a translucent fill bound by `lower`/`upper`; actual line overlays on top for clarity.
- **Comparison mode** offsets the reference series and renders it as a thin dashed line with muted color.
- **Event markers** become vertical dotted lines with tooltip cards pinned near the top; on mobile they convert to badges beneath the chart.
- **Compact mode** hides axes, legend, and annotations, returning only a sparkline plus latest value pill.

### Interaction Model

- Hover sync across all traces with a shared vertical rule; tooltip groups values plus percent deltas vs previous point.
- Click on a legend item toggles visibility; double-click isolates a single series (matching Plotly default behavior).
- Keyboard navigation: `ArrowLeft/Right` steps through time buckets, `Enter` opens the focused tooltip content for screen readers.
- Export controls (PNG/CSV) live in the renderer toolbar but can be disabled via plan options.

### Data Prep Pipeline

1. Validate that the `x` column parses into monotonically increasing timestamps; if gaps exist, optionally backfill null rows for streak continuity.
2. Normalize each series into a long-form dataframe with columns: `ts`, `series_id`, `value`, `axis`, `style`.
3. Apply rolling aggregations when `rolling_window` > 1 and emit both raw and smoothed values for tooltips.
4. When `comparison.mode` is present, duplicate the primary series, shift timestamps by the offset, and tag with `series_id = original + "_cmp"`.
5. Attach event metadata as a separate structure so the renderer can layer annotations without re-querying.

### Renderer Implementation Plan

- **API Surface:** expose `render_timeseries(plan_section: TimeseriesSection) -> RenderArtifact` that returns `{html, metadata}`.
- **Base Figure:** start from `plotly.graph_objects.Figure(layout=BASE_LAYOUT)`; add traces per series with palette pulled from theme tokens.
- **Forecast Handling:** add a `Scatter` trace for `upper` and `lower`, then fill between via `fill='tonexty'` to form the band.
- **Comparison:** render as secondary traces with reduced opacity and dashed lines; include delta calculation in tooltip template.
- **Events:** leverage `add_vline` + `add_annotation`; keep annotations out of the main flow for responsive stacking.
- **Metadata:** emit `{ "series": [...], "events": [...], "axes": {"primary": {...}, "secondary": {...}} }` so downstream consumers know what was plotted.

### Testing Strategy

- Snapshot actual HTML for the base scenario (2 lines + forecast) and compact mode.
- Data-driven pytest parametrization: vary `rolling_window`, `secondary_axis`, and `comparison` flags.
- Contract tests ensuring renderer raises a `PlanValidationError` when required fields (`x.column`, at least one `series`) are missing.
- Visual regression tolerance: configure `pytest-regressions` with a `0.5%` pixel diff budget to allow anti-alias jitter.

### Open Questions

- Do we always receive pre-aggregated data, or should the renderer support inline aggregations (e.g., `series.agg = "sum"`)?
- Should events support multi-line annotations or links that open a detail panel in the host app?
- How does theming flow for currency/number formats—do we honor locale from the plan or global agent settings?

## Renderer Implementation Status

| Operation | Module | Notes | Sample Fixture |
| --- | --- | --- | --- |
| `timeseries` | `renderers/timeseries.py` | Multi-line chart w/ forecast, comparison, events | `tests/data/sample_timeseries.csv` |
| `groupby` | `renderers/groupby.py` | Vertical/horizontal bar charts with reference line | `tests/data/sample_groupby.csv` |
| `composition` | `renderers/composition.py` | Stacked area/bar with optional percentage normalization | `tests/data/sample_composition.csv` |
| `distribution` | `renderers/distribution.py` | Histogram + optional density and boxplot overlays | `tests/data/sample_distribution.csv` |
| `outliers` | `renderers/anomaly.py` | Line + anomaly markers + threshold/event annotations | `tests/data/sample_anomaly.csv` |
| `kpi` | `renderers/kpi.py` | Pure HTML tile grid with delta badges and sparklines | Inline plan payload |

All renderers are wired through `app/registry.py`, surfaced via the CLI (`python -m app.cli render --plan tests/data/sample_plan.json --out build/sample.html`), and covered by regression tests in `tests/test_timeseries_renderer.py`.

## Integration Guidance

- Honor the schema exactly; if a field is missing, log a warning and skip the chart instead of failing hard.
- Accept optional theming parameters (colors, font sizes) so the frontend can rebrand by injecting CSS variables later.
- Emit metadata (e.g., chart ids, used columns) alongside the HTML so telemetry can correlate planner instructions with rendered output.
- Keep Plotly import isolated; when ready we can swap to Grafana/Altair backends using the same registry surface.

## Stretch Goals

- Add an accessibility pass that injects ARIA labels and descriptive text pulled from the plan’s `insight` field.
- Produce PNG exports via `kaleido` for environments that need static artifacts.
- Wire up contract tests that ensure every supported `operation` or `chart.type` has a registered renderer.

## Local Testing

1. Bootstrap a virtual environment and install dependencies:

   ```powershell
   cd Playground/ChartRenderingAgent
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Generate an HTML artifact from the sample plan:

   ```powershell
   python -m app.cli --plan tests/data/sample_plan.json --out build/sample.html
   ```

3. Preview the output via a static server (port `8102` keeps us consistent across agents):

   ```powershell
   cd build
   python -m http.server 8102
   ```

4. Run regression tests before pushing changes:

   ```powershell
   pytest
   ```
