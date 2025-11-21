"""Pytest configuration for Agent Orchestrator integration tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator
import os

import pytest  # type: ignore

_SRC_ROOT = Path(__file__).resolve().parents[1]
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


@pytest.fixture(autouse=True)
def orchestrator_test_environment(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure tests run with deterministic settings and no cached singletons."""

    if "ORCH_PLANNER_MODE" not in os.environ:
        monkeypatch.setenv("ORCH_PLANNER_MODE", "mock")
    monkeypatch.delenv("ORCH_CSV_PROFILER_ENDPOINT", raising=False)

    from agent_orchestrator.settings import reset_settings_cache
    from agent_orchestrator.tools.plan_tool import reset_planner_cache

    reset_planner_cache()
    reset_settings_cache()
    yield
    reset_planner_cache()
    reset_settings_cache()
