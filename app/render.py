import pandas as pd
import plotly.express as px
from typing import Dict, Any


def _groupby(df: pd.DataFrame, x: str, y: str, agg: str):
    if agg == "count":
        grouped = df.groupby(x)[y].count().reset_index(name=y)
    else:
        grouped = df.groupby(x)[y].agg(agg).reset_index()
    return grouped


def render_chart(df: pd.DataFrame, chart_spec: Dict[str, Any]):
    q = chart_spec.get("query", {})
    op = q.get("operation")

    if op == "timeseries_agg":
        x = q.get("x")
        y = q.get("y")
        agg = q.get("agg", "sum")
        grouped = _groupby(df, x, y, agg)
        fig = px.line(grouped, x=x, y=y, title=chart_spec.get("title"))
        return fig

    if op == "groupby_agg":
        x = q.get("x")
        y = q.get("y")
        agg = q.get("agg", "sum")
        grouped = _groupby(df, x, y, agg)
        fig = px.bar(grouped, x=x, y=y, title=chart_spec.get("title"))
        return fig

    if op == "distribution":
        x = q.get("x")
        fig = px.histogram(df, x=x, title=chart_spec.get("title"))
        return fig

    if op == "outliers":
        y = q.get("y")
        fig = px.box(df, y=y, points="outliers", title=chart_spec.get("title"))
        return fig

    # Fallback simple scatter first two columns
    cols = list(df.columns)
    if len(cols) >= 2:
        fig = px.scatter(df.head(500), x=cols[0], y=cols[1], title=chart_spec.get("title", "Fallback"))
        return fig
    fig = px.scatter(title="Empty dataset")
    return fig


def render_dashboard(df: pd.DataFrame, plan: Dict[str, Any]) -> str:
    html_parts = []
    for section in plan.get("sections", []):
        html_parts.append(f"<h2>{section.get('title')}</h2>")
        for chart in section.get("charts", []):
            fig = render_chart(df, chart)
            html_parts.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))
    return "\n".join(html_parts)
