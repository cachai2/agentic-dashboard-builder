Got it — NOT chat-driven, but automatic dashboard generation from a CSV, using an SLM as the planner that decides:


Which charts to create


Which aggregations matter


Which comparisons/outliers are interesting


How to layout the dashboard


What insights should be surfaced automatically


This is a different (and honestly more exciting) scenario.
And yes — this can absolutely be done with SLMs, and there are a few repos close to this pattern.
Let me show you:

✅ Public GitHub Repos Closest to “Automatic Dashboard Generation”
⭐ 1. “AutoPlot” / Automatic EDA + Visualization Tools
These repos automatically analyze a dataset and produce charts, summaries, and dashboards.
🔗 ydata-profiling (formerly pandas-profiling)
https://github.com/ydataai/ydata-profiling


The gold standard for automatic dataset profiling.


Generates:


Histograms


Correlation matrices


Outlier detection


Missing value heatmaps




Produces an HTML report — you can convert to a dashboard.


This is your baseline engine.
Then the SLM acts as the planner on top of the generated metadata.

🔗 AutoViz
https://github.com/AutoViML/AutoViz


Automatically generates:


Distribution plots


Scatterplots


Time-series breakdowns


Group-bys


Interactive dashboards (via Bokeh/Plotly)




Works on CSV directly.


Great backbone for the visualization generation part.

🔗 SweetViz
https://github.com/fbdesignpro/sweetviz


Generates a single HTML data-exploration report.


Great visual summaries.



🔗 Lux (Automatic Visualizations for Pandas)
https://github.com/lux-org/lux


Automatically recommends best visualizations based on data type + structure.


Works inside Pandas dataframes.


Stunning for “What should be plotted?” logic.


This is extremely aligned with automated dashboard generation.

🔗 DataPrep.EDA
https://github.com/sfu-db/dataprep


High-performance automatic EDA:


Correlations


Trend detection


Outlier detection


Type inference




Generates visual summaries.



🔗 Deepchecks Dataset Insights
https://github.com/deepchecks/deepchecks


Automatic dataset validation + insights.



🎯 How these apply to your target use-case
You want this architecture:
[ CSV Upload ]
      ↓
[ Pandas / DuckDB ]
      ↓
[ EDA Engine: AutoViz / ydata-profiling / Lux ]
      ↓
[ SLM Planner on ACA (Serverless GPU) ]
      ↓
[ Dashboard Blueprint ]
      ↓
[ Final Dashboard (Plotly/Streamlit/PowerBI embedded) ]

The SLM’s job is NOT chatting.
Its job is:
🧠 Step 1 — Ingest metadata
From the profiling tools:


Column types


Distribution stats


Correlations


Time-series detection


Cardinality


Outlier presence


🧠 Step 2 — PLAN the dashboard
SLM creates a JSON dashboard spec, e.g.:
{
  "dashboard_title": "Sales Overview",
  "sections": [
    {
      "title": "Trends & Time Series",
      "charts": [
        {
          "type": "line",
          "x": "date",
          "y": "revenue",
            "aggregate": "sum"
        }
      ]
    },
    {
      "title": "Outliers",
      "charts": [
        {
          "type": "scatter",
          "x": "region",
          "y": "revenue",
          "highlight": "outliers"
        }
      ]
    }
  ]
}

🧠 Step 3 — Dashboard Renderer
Render with:


Plotly


Streamlit


Grafana JSON


PowerBI Embedded via SDK


or your ACA web app


This is exactly a “planner agent” workload, perfect for an SLM.

🔍 So… Are there repos that combine LLM + Automatic Viz?
Yes, but fewer. The best ones:

⭐ 1. GPT-Pilot-EDA
https://github.com/ninilinux/gpt-pilot-eda
Uses an LLM to generate EDA scripts and visualizations AUTOMATICALLY from CSV.

⭐ 2. Pandas AI (Automatic analysis + charts)
https://github.com/Sinaptik-AI/pandas-ai


Has automatic chart generation via LLMs.


You can provide a CSV and ask it to “generate insights” — it outputs charts + reasoning.


Replace the LLM with your SLM on ACA.

⭐ 3. Auto-Analyst (“Talk to data, auto-generate visuals”)
https://github.com/sail-sg/auto-analyst


LLM-based automatic data analysis.


Generates:


summaries


visualizations


insights


code
based on a dataset.




Very close.

⭐ 4. Genie (Data → Insights → Visualization)
https://github.com/vercel-labs/genie


LLM-powered data insight engine.


Generates:


chart code


SQL


visualizations




Good inspiration for your pattern.



🎯 Which Ones Should You Combine for ACA Demo?
Best combo for a POC:
🥇 1. ydata-profiling
→ For deep automatic metadata extraction.
🥇 2. Lux
→ For identifying the “best” visualizations.
🥇 3. An SLM (phi-4, phi-3, llama-3-instruct)
→ To generate the dashboard spec from the metadata.
🥇 4. Plotly / Streamlit
→ Render the actual dashboards.

🚀 Want me to create:
✔ a complete blueprint (architecture)
✔ a JSON schema for the “Dashboard Plan”
✔ a code skeleton (Python FastAPI + ACA session + SLM + tools)
✔ or a full demo script you can show at Ignite?
Just tell me and I’ll draft the whole thing.