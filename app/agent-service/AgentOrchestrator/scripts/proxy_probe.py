import json
from pathlib import Path

import httpx

workspace_root = Path(__file__).resolve().parents[2]
schema_path = workspace_root / "CsvProfilerAgent" / "schemas" / "dashboard_plan.schema.json"
schema = json.loads(schema_path.read_text())

messages = [
    {"role": "system", "content": "You are a dashboard planner."},
    {"role": "user", "content": json.dumps({"dataset_name": "sample"})},
]

payload = {
    "messages": messages,
    "schema": schema,
    "model": "llama3.1:8b",
    "temperature": 0.1,
    "stream": False,
}

response = httpx.post("http://127.0.0.1:8000/json", json=payload)
print("status:", response.status_code)
print(response.text[:4000])
