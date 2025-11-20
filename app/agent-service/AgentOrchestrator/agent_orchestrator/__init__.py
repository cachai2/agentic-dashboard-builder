"""Agent Orchestrator package wiring Playground agents into Microsoft Agent Framework."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is importable so we can reuse sibling agent packages.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

__all__ = ["_REPO_ROOT"]
