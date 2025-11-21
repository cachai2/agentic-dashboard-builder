"""Structured JSON planner agent reused by the orchestrator."""

from .app.service import app as ollama_app

__all__ = ["ollama_app"]
