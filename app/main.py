import io
import uuid
import json
from typing import Dict, Any

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from jsonschema import validate, ValidationError

from .settings import get_settings
from .profiling import generate_profile_summary
from .planner import plan_dashboard
from .render import render_dashboard

settings = get_settings()
app = FastAPI(title="Ignite Auto Dashboard")

SESSIONS: Dict[str, Dict[str, Any]] = {}

class DashboardPlan(BaseModel):
    title: str
    description: str | None = None
    priority: str | None = None
    sections: list[Dict[str, Any]]


# Load schema once
with open(settings.dashboard_plan_schema_path, "r", encoding="utf-8") as f:
    PLAN_SCHEMA = json.load(f)


def _validate_plan(plan: Dict[str, Any]) -> bool:
    try:
        validate(plan, PLAN_SCHEMA)
        return True
    except ValidationError:
        return False


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files supported")
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {"df": df}
    return {"session_id": session_id, "rows": len(df), "columns": list(df.columns)}


@app.post("/dashboard/plan", response_model=DashboardPlan)
async def dashboard_plan(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    df: pd.DataFrame = session["df"]

    profile = generate_profile_summary(df)
    plan = plan_dashboard(profile)

    if not _validate_plan(plan):
        # Fallback minimal plan
        plan = {
            "title": "Fallback Dashboard",
            "sections": [
                {
                    "title": "Summary",
                    "charts": [
                        {
                            "id": "row_count",
                            "title": "Row Count",
                            "type": "table",
                            "query": {"operation": "distribution", "x": list(df.columns)[0] if df.columns.any() else "value"},
                            "insight": f"Dataset has {len(df)} rows."
                        }
                    ]
                }
            ]
        }

    session["plan"] = plan
    return plan


@app.get("/dashboard/view")
async def dashboard_view(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    df: pd.DataFrame = session["df"]
    plan: Dict[str, Any] = session.get("plan")
    if not plan:
        raise HTTPException(status_code=400, detail="No plan generated yet")

    html = render_dashboard(df, plan)
    return {"html": html}


@app.get("/health")
async def health():
    return {"status": "ok"}
