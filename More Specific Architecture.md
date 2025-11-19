Awesome, let’s make this real. I’ll give you:

Architecture blueprint (ACA + SLM + EDA engine)

DashboardPlan JSON schema + example

Python/FastAPI code skeleton (agent + tools)

ACA deployment shape & scaling notes

Demo walkthrough script (how to present it)

1. Architecture blueprint

Goal:
Upload a CSV → SLM analyzes metadata + profiling output → produces a dashboard plan → backend renders plots → user sees an auto-built dashboard. No chat, just “Upload → Boom, dashboard.”

Components

(A) Frontend (simple web app)

Allows:

CSV upload

Maybe a few options: “Business metrics” / “Data quality” / “Exploratory”

Calls backend:

POST /upload → returns session_id

POST /dashboard/plan?session_id=...

GET /dashboard/view?session_id=... (or just returns HTML/JSON describing charts)

(B) ACA backend app (CPU)

Endpoints:

/upload – stores CSV to Blob/Volume; loads into DuckDB/Pandas.

/profile – runs ydata-profiling / Lux / AutoViz / custom EDA.

/dashboard/plan – calls GPU agent (SLM) with:

Schema

Summary stats

EDA outputs (high-level)

/dashboard/render – builds Plotly/Altair/Matplotlib visual specs from the DashboardPlan.

(C) ACA agent app (GPU, SLM)

Runs:

SLM (phi-3/phi-4/llama-3-small-like) on serverless GPU.

Exposes /plan_dashboard:

Input: JSON with schema, summaries, correlations, optional “intent” (e.g. business, data-quality).

Output: DashboardPlan JSON (sections, charts, each chart’s query + encoding).

(D) Storage / Data layer

CSV stored in:

Blob, or

Mounted Azure Files / Ephemeral volume

Data frame in memory or DuckDB database per session.

(E) Telemetry

App Insights:

Track end-to-end latency.

Track GPU utilization & concurrent sessions.

Track “charts per dashboard” etc.

2. DashboardPlan JSON schema

This is what the SLM returns. You want it:

Simple

Composable

Easy to turn into Plotly/Altair/Power BI later.

2.1. Schema (conceptual)
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DashboardPlan",
  "type": "object",
  "required": ["title", "sections"],
  "properties": {
    "title": { "type": "string" },
    "description": { "type": "string" },
    "priority": {
      "type": "string",
      "enum": ["overview", "deep-dive", "data-quality"]
    },
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["title", "charts"],
        "properties": {
          "title": { "type": "string" },
          "description": { "type": "string" },
          "charts": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["id", "type", "query"],
              "properties": {
                "id": { "type": "string" },
                "title": { "type": "string" },
                "insight": { "type": "string" },
                "type": {
                  "type": "string",
                  "enum": [
                    "line",
                    "bar",
                    "stacked_bar",
                    "area",
                    "scatter",
                    "box",
                    "histogram",
                    "heatmap",
                    "table",
                    "kpi"
                  ]
                },
                "query": {
                  "type": "object",
                  "required": ["operation"],
                  "properties": {
                    "operation": {
                      "type": "string",
                      "enum": [
                        "groupby_agg",
                        "timeseries_agg",
                        "topk",
                        "distribution",
                        "correlation_matrix",
                        "outliers"
                      ]
                    },
                    "x": { "type": "string" },
                    "y": { "type": "string" },
                    "group": { "type": "string" },
                    "filters": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "column": { "type": "string" },
                          "op": {
                            "type": "string",
                            "enum": ["=", "!=", ">", "<", ">=", "<=", "in", "not in"]
                          },
                          "value": {}
                        }
                      }
                    },
                    "agg": {
                      "type": "string",
                      "enum": ["sum", "avg", "count", "min", "max", "median"]
                    },
                    "top_k": { "type": "integer" },
                    "time_grain": {
                      "type": "string",
                      "enum": ["day", "week", "month", "quarter", "year"]
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}

2.2. Example DashboardPlan from SLM
{
  "title": "E-commerce Sales Overview",
  "description": "Automatic dashboard highlighting trends, segments, and outliers in the dataset.",
  "priority": "overview",
  "sections": [
    {
      "title": "Overall Revenue Trend",
      "description": "How revenue evolves over time at a high level.",
      "charts": [
        {
          "id": "rev_timeseries",
          "title": "Revenue Over Time",
          "insight": "Total revenue is trending upwards with visible spikes around month-end.",
          "type": "line",
          "query": {
            "operation": "timeseries_agg",
            "x": "order_date",
            "y": "revenue",
            "agg": "sum",
            "time_grain": "month"
          }
        },
        {
          "id": "rev_by_category",
          "title": "Revenue by Category",
          "insight": "Electronics and Home lead revenue; Apparel is a smaller but growing segment.",
          "type": "bar",
          "query": {
            "operation": "groupby_agg",
            "x": "category",
            "y": "revenue",
            "agg": "sum",
            "top_k": 10
          }
        }
      ]
    },
    {
      "title": "Customer & Region Insights",
      "description": "Focus on how regions contribute to performance.",
      "charts": [
        {
          "id": "rev_by_region",
          "title": "Revenue by Region",
          "insight": "North America is the largest market; EMEA has the highest recent growth.",
          "type": "stacked_bar",
          "query": {
            "operation": "groupby_agg",
            "x": "region",
            "y": "revenue",
            "group": "category",
            "agg": "sum"
          }
        }
      ]
    },
    {
      "title": "Outliers & Data Quality",
      "description": "Spot unusual values and missing data.",
      "charts": [
        {
          "id": "order_value_outliers",
          "title": "Order Value Outliers",
          "insight": "A few very large orders skew average revenue; consider capping for analysis.",
          "type": "box",
          "query": {
            "operation": "outliers",
            "y": "revenue"
          }
        }
      ]
    }
  ]
}

3. Python/FastAPI code skeleton (agent + tools)

Think: CPU app orchestrates EDA + dashboard rendering, GPU app does the planning.

Below is one-container version for simplicity (you can split CPU/GPU later).

3.1. Backend skeleton (FastAPI app)
# app/main.py
import uuid
import io
from typing import Dict, Any

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

# Pretend these are your internal modules
from .profiling import generate_profile_summary
from .slm_planner import plan_dashboard
from .render import render_dashboard_spec

app = FastAPI()

# In-memory store just for demo; in prod, use Redis/Blob/etc
SESSIONS: Dict[str, Dict[str, Any]] = {}


class DashboardPlan(BaseModel):
    title: str
    description: str | None = None
    priority: str | None = None
    sections: list[Dict[str, Any]]


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {"df": df}

    return {"session_id": session_id, "rows": len(df), "columns": list(df.columns)}


@app.post("/dashboard/plan", response_model=DashboardPlan)
async def generate_dashboard_plan(session_id: str):
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    df: pd.DataFrame = session["df"]

    # 1) Run EDA/profiling to create structured metadata for the model
    profile_summary = generate_profile_summary(df)
    # e.g. { "schema": [...], "stats": {...}, "correlations": {...}, ... }

    # 2) Call SLM planner (hosted on ACA GPU or Azure AI endpoint)
    plan_dict = plan_dashboard(profile_summary)

    # 3) Persist the plan for later rendering
    session["dashboard_plan"] = plan_dict

    return plan_dict


@app.get("/dashboard/view")
async def get_dashboard_view(session_id: str):
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    df: pd.DataFrame = session["df"]
    plan_dict: Dict[str, Any] | None = session.get("dashboard_plan")

    if plan_dict is None:
        raise HTTPException(status_code=400, detail="No dashboard plan. Call /dashboard/plan first.")

    # 4) Render dashboard into a UI-friendly representation
    dashboard_html = render_dashboard_spec(df, plan_dict)

    # For a demo, you can just return HTML and let frontend embed it
    return {"html": dashboard_html}

3.2. Profiling module (EDA engine integration)
# app/profiling.py
import pandas as pd

def generate_profile_summary(df: pd.DataFrame) -> dict:
    """
    Return a compact JSON summary suitable for the SLM.

    Suggestion:
    - Column names, inferred types
    - Basic stats (min, max, mean, null %, distinct count)
    - Flags: is_time_series, is_categorical, etc.
    - Maybe top N correlations
    """
    schema = []
    for col in df.columns:
        series = df[col]
        schema.append({
            "name": col,
            "dtype": str(series.dtype),
            "non_null_count": int(series.notnull().sum()),
            "null_ratio": float(series.isnull().mean()),
            "unique_values": int(series.nunique()),
            "example_values": [str(v) for v in series.dropna().unique()[:5]],
        })

    summary = {
        "row_count": len(df),
        "schema": schema,
        # TODO: plug in ydata-profiling, Lux, AutoViz, etc
        # "correlations": ...,
        # "distributions": ...,
    }
    return summary

3.3. SLM planner module (calls your GPU-based SLM)

You can either:

Call an internal ACA GPU endpoint (self-hosted SLM), or

Call Azure AI model (phi-3/phi-4/etc) from here.

Skeleton:

# app/slm_planner.py
import os
import httpx
import json

SML_PLANNER_ENDPOINT = os.getenv("SLM_PLANNER_ENDPOINT")  # e.g. another ACA app

SYSTEM_PROMPT = """
You are a data visualization planner.

You receive:
- A dataset profile (schema + basic stats)
Your job:
- Propose an optimal dashboard plan in JSON.
- Focus on trends, segment comparisons, and outliers.
- Use the DashboardPlan schema.
- Do NOT invent columns that are not present in schema.
"""

def plan_dashboard(profile_summary: dict) -> dict:
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "Here is the dataset profile. Return ONLY valid JSON DashboardPlan.",
            },
            {
                "role": "user",
                "content": json.dumps(profile_summary),
            }
        ]
    }

    # Example: call a custom SLM endpoint (e.g., FastAPI wrapper around vLLM/phi)
    # Adapt to whatever protocol your agent uses.
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{SML_PLANNER_ENDPOINT}/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

    # Assuming OpenAI-style response:
    raw_text = data["choices"][0]["message"]["content"]
    plan_dict = json.loads(raw_text)
    return plan_dict

3.4. Render module (construct charts from plan)
# app/render.py
import pandas as pd
import plotly.express as px
from jinja2 import Template

def render_chart(df: pd.DataFrame, chart_spec: dict):
    q = chart_spec["query"]
    op = q["operation"]

    # Example: handle a timeseries_agg
    if op == "timeseries_agg":
        x = q["x"]
        y = q["y"]
        agg = q.get("agg", "sum")
        # naive implementation; in real code, handle dtypes/time_grain properly
        grouped = df.groupby(x)[y].agg(agg).reset_index()
        fig = px.line(grouped, x=x, y=y, title=chart_spec.get("title"))
        return fig

    # ... implement groupby_agg, topk, distribution, outliers, etc.

    # Fallback: show a table
    return px.scatter(df.head(100), x=df.columns[0], y=df.columns[1])

def render_dashboard_spec(df: pd.DataFrame, plan: dict) -> str:
    figs_html = []

    for section in plan.get("sections", []):
        for chart in section.get("charts", []):
            fig = render_chart(df, chart)
            figs_html.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))

    # Super simple layout; use Jinja2 template for nicer formatting
    template_str = """
    <html>
    <head><title>{{ title }}</title></head>
    <body>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
      {% for section, charts in sections %}
        <h2>{{ section.title }}</h2>
        <p>{{ section.description }}</p>
        {% for chart_html in charts %}
          <div style="margin-bottom: 32px;">{{ chart_html | safe }}</div>
        {% endfor %}
      {% endfor %}
    </body>
    </html>
    """

    # Group charts by section
    sections_payload = []
    index = 0
    for section in plan.get("sections", []):
        count = len(section.get("charts", []))
        charts = figs_html[index:index+count]
        index += count
        sections_payload.append((section, charts))

    html = Template(template_str).render(
        title=plan.get("title", "Auto Dashboard"),
        description=plan.get("description", ""),
        sections=sections_payload,
    )
    return html

4. ACA deployment & serverless GPU notes

For a clean ACA story, you can present two options:

Single container image

Houses:

SLM runtime (e.g., vLLM with small model)

FastAPI API (planner + data logic)

Create a GPU workload profile in ACA and deploy this app there.

Use ACA scale rules (e.g., HTTP concurrency / RPS) to scale GPU replicas.

Two apps in one ACA environment

App A (CPU): FastAPI for upload/profiling/rendering (no GPU).

App B (GPU): SLM planner app (just /chat/completions or /plan_dashboard).

Both in same Container Apps Environment; talk over internal DNS.

App B uses GPU workload profile + scale-to-zero enabled.

In both, you get to say:

“Idle = $0 (if no traffic).”

“Bursty load → auto-scale GPU pods.”

“All data stays in your virtual network environment.”

5. Demo walkthrough script (for a talk or customer)

Here’s a simple talk track you can literally read/adjust:

1. Setup the scenario
“Imagine your data team gets a CSV from sales, marketing, or operations. Instead of spending hours manually building dashboards, they just drop the file into this app and get a first-pass dashboard in seconds.”

2. Upload the CSV
(Switch to the UI)
“I’ll upload a sample e-commerce dataset with order_date, region, category, revenue, and customer info.”

Show the file picker, upload.

Backend logs show /upload request.

3. Trigger auto-dashboard generation
“Now I click ‘Generate Dashboard’. Behind the scenes, three things happen:

Profiling: We run some quick EDA—type inference, summary stats, and correlations.

Planning with a Small Language Model: We send that metadata to a small model running on Azure Container Apps with serverless GPUs. The model chooses what charts to build: time series, segments, and outliers.

Rendering: We translate the model’s JSON plan into Plotly charts and compile the dashboard.”

4. Show the dashboard

Scroll through sections:

“Here’s the overall revenue trend over time.”

“Here’s revenue by category and by region.”

“And here’s an outlier view that shows unusually large orders.”

Call out that:

You did not hand-author any chart config for this dataset.

The model’s plan is completely data-driven.

5. Highlight ACA + SLM value
“This is powered by:

Azure Container Apps with serverless GPUs, so the SLM planner can scale with demand and scale back to zero when unused.

A small model, which is cheaper and faster than huge LLMs, but still smart enough to pick sensible dashboards.

The agent pattern: the model doesn’t crunch raw data—it just plans, and our tools (Pandas/DuckDB + Plotly) do the heavy lifting.”

6. Optional variant: upload a different CSV

Show how the same pipeline adapts to a different domain dataset:

HR attrition dataset, or

Marketing campaign performance.

Emphasize: “I didn’t change any prompts or code; the planner adapts to the schema.”

If you want, next I can:

Tighten the system prompt specifically for phi-like SLMs.

Add guardrails (e.g., JSON schema enforcement, retries).

Or tailor this to Azure AI Foundry + ACA specifically (tooling, resource names, etc.) so you can plug it into your existing Ignite demos.