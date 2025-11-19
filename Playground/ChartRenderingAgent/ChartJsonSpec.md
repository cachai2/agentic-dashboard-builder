# Chart JSON Specification

This document captures the canonical request contract for the Chart Rendering Agent. Each section in a `DashboardPlan` must include an `operation` field that maps to a renderer registered in `app/registry.py`, and ultimately surfaced through `app/cli.py`.

Every renderer returns a `RenderArtifact` with two keys:

- `html`: embeddable markup (Plotly figure divs or bespoke HTML fragments)
- `metadata`: JSON summary (series, axes, stats) that downstream systems can log or inspect without scraping the HTML

## Dashboard Payload Skeleton

```json
{
  "datasets": [
    {"id": "rev", "path": "tests/data/sample_timeseries.csv", "format": "csv"}
  ],
  "sections": [
    {"operation": "timeseries", ...},
    {"operation": "groupby", ...}
  ]
}
```

Datasets reference CSV files relative to the plan path. Section objects refer to datasets by `dataset`. When an operation does not require data (e.g., KPI tiles), the `dataset` field is omitted.

---

## Timeseries (`renderers/timeseries.py`)

**Purpose:** multi-line temporal charts with forecast bands, prior-period overlays, optional rolling averages, and event annotations.

### Sketch — Timeseries

```text
Revenue vs Target
  │          forecast band
  │ rev  /\        ___
  │     /  \______/   \__   target (dashed)
  │____/__________________ time →
  ┆ annotations drop from dotted event lines
```

### Plan Fields — Timeseries

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `operation` | string | yes | Must be `"timeseries"` |
| `title` | string | no | Composer renders as `<h2>` |
| `dataset` | string | yes | References `datasets[].id` |
| `x` | object | yes | `{ "column": "date", "grain": "day" }` |
| `series` | array | yes | Each `{ "id", "column", "label?", "axis?", "style?" }` |
| `forecast` | object | no | `{ "lower": "col", "upper": "col", "label?" }` |
| `comparison` | object | no | `{ "mode": "previous_period", "offset_days": 7 }` |
| `events` | array | no | `{ "ts": ISO-8601, "label": str, "annotation?": str }` |
| `options` | object | no | `{ "compact": false, "y_axis_format": "currency", "rolling_window": 7 }` |

**Example:** see the first section in `tests/data/sample_plan.json`.

### Renderer Output Metadata — Timeseries

```json
{
  "series": [{"id": "actual", "column": "revenue", "axis": "primary"}],
  "forecast": {"lower": "yhat_lower", "upper": "yhat_upper", "label": "Forecast"},
  "comparison": {"mode": "previous_period", "offset_days": 7},
  "events": [{"ts": "2024-09-05T00:00:00", "label": "Promo Start"}],
  "axes": {
    "x": {"column": "date", "grain": "day"},
    "y_primary": {"format": "currency"},
    "y_secondary": {"enabled": false}
  }
}
```

---

## GroupBy / Comparative Bars (`renderers/groupby.py`)

**Purpose:** categorical comparisons with optional reference lines, automatic orientation switching, and Top-N limiting.

### Sketch — GroupBy Bars

```text
Revenue by Region
West   ████████████████  $4.2M
East   ████████████      $3.1M
──────── reference mean line
```

### Plan Fields — GroupBy Bars

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `operation` | string | yes | `"groupby"` |
| `dataset` | string | yes | Category + metric source |
| `dimension` | string | yes | Column name (e.g., region) |
| `metric` | string | yes | Column to aggregate |
| `aggregation` | string | no | `sum` (default), `avg`, `mean`, or `count` |
| `options.orientation` | string | no | `vertical` (default) or `horizontal` |
| `options.sort` | string | no | `desc` (default), `asc`, or `none` |
| `options.limit` | int | no | Top-N filter (default 6) |
| `options.show_reference` | bool | no | Adds mean/reference line |
| `options.reference_value` | number | no | Overrides computed mean |

### Renderer Output Metadata — GroupBy Bars

```json
{
  "operation": "groupby",
  "dimension": "region",
  "metric": "revenue",
  "aggregation": "sum",
  "limit": 5
}
```

---

## Composition (`renderers/composition.py`)

**Purpose:** stacked area (time) or stacked bar (single period) charts to show mix changes, optionally normalized to percentages.

### Sketch — Composition

```text
Product Mix (% of revenue)
100% ───────── services ███
 75% ──────── product_b ████
 25%
   0%────────────────────────── time →
```

### Plan Fields — Composition

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `operation` | string | yes | `"composition"` |
| `dataset` | string | yes | Data source |
| `x` | object | conditional | Required for stacked-area; optional for stacked-bar |
| `stacks` | array | yes | Column names comprising the stack |
| `options.normalize` | bool | no | Default `false`; when `true` values become percentages |
| `options.kind` | string | no | `stacked_area` (default) or `stacked_bar` |

**Metadata:** `{ "operation": "composition", "stacks": ["services", "product_b"], "normalize": true, "kind": "stacked_area" }`

---

## Distribution (`renderers/distribution.py`)

**Purpose:** histograms with optional density overlays plus horizontal boxplots for quick spread analysis.

### Sketch — Distribution

```text
Latency Histogram
Count │      ■■
  │    ■■■■■     density curve
  │  ■■■■■■■■  ~~~~~~~
  │■■■■■■■■■■■■~~~~~~~
  └──────────────────── ms
        ───────── boxplot ───────
```

### Plan Fields — Distribution

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `operation` | string | yes | `"distribution"` |
| `dataset` | string | yes | Metric source |
| `metric` | string | yes | Column to analyze |
| `comparison_metric` | string | no | Reserved for future overlay support |
| `options.bins` | int | no | Default `30` |
| `options.overlay` | string | no | `density` (default) or `none` |
| `options.show_boxplot` | bool | no | Adds horizontal boxplot glyph |

**Metadata:**

```json
{
  "operation": "distribution",
  "metric": "latency_ms",
  "bins": 30,
  "stats": {"count": 20, "mean": 156.2, "median": 157.0, "std": 19.5}
}
```

---

## Outliers / Anomaly (`renderers/anomaly.py`)

**Purpose:** line-plus-marker chart that highlights threshold breaches or pre-flagged anomalies with optional annotations.

### Sketch — Outliers

```text
Error Rate Monitoring
0.06 ── threshold (orange dashed)
0.05 ──○────○─◎──○
0.04 ─○──○──○──◎──○  ◎ = anomaly marker
  └──────────────── time →
```

### Plan Fields — Outliers

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `operation` | string | yes | `"outliers"` |
| `dataset` | string | yes | Time series source |
| `x` | object | yes | Timestamp column metadata |
| `y` | string | yes | Metric column |
| `threshold` | object | no | `{ "value": 0.04, "direction": "above" }` |
| `flag_column` | string | no | Boolean/int marker column overriding threshold logic |
| `events` | array | no | Same shape as timeseries events |

**Metadata:** `{ "operation": "outliers", "y": "error_rate", "threshold": {"value": 0.04, "direction": "above"}, "anomaly_count": 2 }`

---

## KPI Cards (`renderers/kpi.py`)

**Purpose:** lightweight HTML tiles with headline metrics, delta badges, and inline sparklines. Does **not** require a dataset.

### Sketch — KPI Cards

```text
┌────────────────┬────────────────┬────────────────┐
│ Net Revenue    │ NPS            │ Churn          │
│ $1.28M  ↑12%   │ 52   →         │ 3.1%  ↓0.4pp   │
│ sparkline ▂▄▆█ │ sparkline ▃█▂  │ sparkline ▂▁▃█ │
└────────────────┴────────────────┴────────────────┘
```

### Plan Fields — KPI Cards

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `operation` | string | yes | `"kpi"` |
| `title` | string | no | Optional group heading |
| `layout` | string | no | `grid` (default) or `row` |
| `cards` | array | yes | Each element described below |

### Card Object

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | yes | Display label |
| `value` | number/string | yes | Big number |
| `unit` | string | no | Prefix or suffix applied to `value` |
| `delta` | object | no | `{ "value": 0.12, "direction": "up", "label": "vs last month" }` |
| `trend` | array | no | List of numeric sparkline points |
| `trend_label` | string | no | Screen-reader hint |

**Metadata:** `{ "operation": "kpi", "card_count": 3, "layout": "grid", "cards": [...] }`

---

## Validation & Testing

- The sample payload `tests/data/sample_plan.json` exercises every chart type.
- Run the automated suite:

```powershell
cd Playground/ChartRenderingAgent
\.venv\Scripts\python -m pytest
```

- Manual rendering via CLI:

```powershell
cd Playground/ChartRenderingAgent
\.venv\Scripts\python -m app.cli render --plan tests/data/sample_plan.json --out build/sample.html
```

The generated HTML bundles Plotly assets via CDN and opens directly in any browser.
