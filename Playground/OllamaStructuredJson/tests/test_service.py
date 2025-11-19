import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("OLLAMA_MODE", "mock")

from fastapi.testclient import TestClient  # noqa: E402

from app.service import app, client  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def test_plan_endpoint_returns_valid_plan():
    client = TestClient(app)
    profile = json.loads((SAMPLES / "profile_summary.json").read_text())
    response = client.post(
        "/plan",
        json={"profile_summary": profile, "prompt_version": "v1", "session_id": "test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["sections"], "Plan should include sections"
    assert payload["metadata"]["round_trips"] == 1


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["mode"] == "mock"


def test_plan_endpoint_retries_when_initial_response_invalid(monkeypatch):
    test_client = TestClient(app)
    profile = json.loads((SAMPLES / "profile_summary.json").read_text())

    responses = ["not json", (SAMPLES / "mock_plan.json").read_text()]
    call_tracker = {"count": 0}

    def fake_generate_prompt(prompt_bundle):
        idx = min(call_tracker["count"], len(responses) - 1)
        call_tracker["count"] += 1
        return responses[idx]

    monkeypatch.setattr(client, "generate_plan_text", fake_generate_prompt)

    response = test_client.post(
        "/plan",
        json={"profile_summary": profile, "prompt_version": "v1", "session_id": "retry"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["round_trips"] == 2
    assert call_tracker["count"] == 2
