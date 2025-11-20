"""Quick helper to probe the planner gateway."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

SCHEMA_PATH = Path("schemas/dashboard_plan.schema.json")


def main(use_plan_schema: bool = False) -> None:
    schema = {
        "type": "object",
        "properties": {"greeting": {"type": "string"}},
        "required": ["greeting"],
    }
    if use_plan_schema and SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    payload = {
        "messages": [
            {"role": "system", "content": "You are JSON echo bot."},
            {"role": "user", "content": "Say hi using valid JSON."},
        ],
        "schema": schema,
        "model": "llama3.1:8b",
        "temperature": 0.1,
        "stream": False,
    }

    resp = httpx.post("http://127.0.0.1:8801/json", json=payload, timeout=60.0)
    print(resp.status_code)
    print(resp.text[:400])


if __name__ == "__main__":
    main(use_plan_schema=True)
