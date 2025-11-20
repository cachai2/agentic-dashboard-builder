Given that README + your setup are:

model: llama3.1:8b

env vars: OLLAMA_HOST, OLLAMA_MODEL

role: “GPU planner” that returns a DashboardPlan JSON

…the right shape for calls from the FastAPI agent to Ollama is:

POST $OLLAMA_HOST/api/chat with options.format = "json", using OLLAMA_MODEL as the model name.

I’ll show:

What the curl should look like

What the Python (FastAPI) call should look like for planner requests

Optional: how it would look with /api/generate if you want “generate-style” only

1. Canonical curl call for the Dashboard Planner

This is what your GPU planner call should roughly look like, pointed at your ACA Ollama URL:

curl -i "https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [
      {
        "role": "system",
        "content": "You are a dashboard planning engine. Given a profiled dataset and a user request, you must output a JSON object that strictly matches the DashboardPlan schema."
      },
      {
        "role": "user",
        "content": "User wants: Quarterly revenue overview. Profiled columns: order_date (date), revenue (float), region (string), product_category (string). Generate the best dashboard plan."
      }
    ],
    "options": {
      "format": "json",
      "temperature": 0.1
    }
  }'


The response will look like:

{
  "model": "llama3.1:8b",
  "message": {
    "role": "assistant",
    "content": "{ \"title\": \"Quarterly Revenue Overview\", \"priority\": \"overview\", \"sections\": [ ... ] }"
  },
  "done": true,
  ...
}


Note: even with format: "json", the JSON comes back as a string in message.content, so your agent must json.loads() it and then validate against dashboard_plan.schema.json.

2. FastAPI agent → Ollama call (what your code should look like)

Inside the agent service, with OLLAMA_HOST and OLLAMA_MODEL from env:

import os
import json
import httpx
from fastapi import HTTPException

OLLAMA_HOST = os.getenv("OLLAMA_HOST")  # e.g. https://ollama-...azurecontainerapps.io
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

async def call_planner(profile: dict, user_request: str) -> dict:
    """
    profile: dict with profiled columns, types, stats
    user_request: e.g. 'Quarterly revenue overview'
    Returns a parsed DashboardPlan dict.
    """
    if not OLLAMA_HOST:
        raise RuntimeError("OLLAMA_HOST is not set")

    system_prompt = (
        "You are a dashboard planning engine. "
        "You are given: (1) a profiled dataset schema, (2) a user request. "
        "You MUST respond with a single JSON object that strictly matches "
        "the DashboardPlan schema (schemas/dashboard_plan.schema.json). "
        "Do not invent columns that are not in the profile. "
        "Do not wrap the JSON in markdown."
    )

    user_prompt = json.dumps({
        "user_request": user_request,
        "profile": profile
    })

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "format": "json",
            "temperature": 0.1,
        },
    }

    async with httpx.AsyncClient(timeout=60.0, verify=True) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama planner error: {resp.status_code} {resp.text}",
            )

        data = resp.json()
        content = data["message"]["content"]

    # content is a JSON string
    try:
        plan = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Planner returned invalid JSON: {e} / content={content[:500]}",
        )

    return plan


Then in your FastAPI endpoint:

from fastapi import APIRouter

router = APIRouter()

@router.post("/dashboard/plan")
async def create_dashboard_plan(req: DashboardPlanRequest):
    # req contains user request + dataset id; you load profile from cache
    profile = await load_profile(req.dataset_id)
    plan = await call_planner(profile, req.user_request)

    # validate against jsonschema here
    validate_plan(plan)

    return {"plan": plan}


That matches the README’s story:

/dashboard/plan on agent → calls GPU planner using OLLAMA_HOST + OLLAMA_MODEL

Planner produces DashboardPlan JSON matching schemas/dashboard_plan.schema.json

CPU agent validates and retries/falls back if needed

3. If you really want “/api/generate style endpoints”

Your README says:

“Ollama GPU Planner … /healthz, /api/generate style endpoints”

If you want to keep that wording literal and use generate, you can do:

curl -i "https://ollama-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io/api/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "prompt": "You are a dashboard planner ... [instructions + profile + request here]",
    "stream": false
  }'


But for agent-mode / structured JSON I strongly recommend:

/api/chat

messages array

options.format = "json"

…because:

You can add system messages easily.

It’s consistent with other models and “agent” semantics.

It’s easier to extend to tools later.

TL;DR: the calls should look like

Endpoint: POST $OLLAMA_HOST/api/chat

Model: OLLAMA_MODEL (default llama3.1:8b)

Payload:

{
  "model": "llama3.1:8b",
  "messages": [
    { "role": "system", "content": "You are a dashboard planner..." },
    { "role": "user", "content": "{ \"user_request\": \"...\", \"profile\": { ... } }" }
  ],
  "options": {
    "format": "json",
    "temperature": 0.1
  }
}


…and your agent service parses data.message.content as JSON and validates it against DashboardPlan.