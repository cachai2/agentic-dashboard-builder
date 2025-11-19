"""Simulate a Microsoft Agent Framework tool invocation against the FastAPI surface."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import DashboardPlan

SAMPLE_PATH = Path("samples/retail_superstore_sample.csv")


def main() -> None:
    csv_bytes = SAMPLE_PATH.read_bytes()

    client = TestClient(app)
    response = client.post(
        "/profile",
        params={"dataset_name": "retail_superstore", "max_rows": 5000},
        content=csv_bytes,
        headers={"Content-Type": "text/csv"},
    )
    response.raise_for_status()

    payload = response.json()
    DashboardPlan.model_validate(payload)

    print("Simulated tool call succeeded. Response summary:")
    print(json.dumps({
        "dataset_name": payload.get("dataset_name"),
        "row_count": payload.get("row_count"),
        "sampling_ratio": payload.get("sampling_ratio"),
        "column_count": payload.get("column_count"),
    }, indent=2))


if __name__ == "__main__":
    main()
