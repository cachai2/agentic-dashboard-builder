from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import httpx

from .config import Settings, get_settings


class OllamaClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._http_client: httpx.Client | None = None

    def _ensure_client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=self.settings.ollama_timeout_seconds)
        return self._http_client

    def generate_plan_text(self, payload: Dict[str, str], response_schema: Dict[str, Any] | None = None) -> str:
        mode = self.settings.ollama_mode
        if mode == "mock":
            return self._load_mock_plan()
        schema_payload = response_schema if self.settings.ollama_send_json_schema else None
        return self._call_remote(payload, schema_payload)

    def _load_mock_plan(self) -> str:
        mock_path = Path(__file__).resolve().parent.parent / "samples" / "mock_plan.json"
        return mock_path.read_text(encoding="utf-8")

    def _call_remote(self, prompts: Dict[str, str], response_schema: Dict[str, Any] | None = None) -> str:
        client = self._ensure_client()
        body = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": prompts["system"]},
                {"role": "user", "content": prompts["user"]},
            ],
            "stream": False,
        }
        if response_schema:
            body["format"] = response_schema
        elif self.settings.ollama_force_json_mode:
            body["format"] = "json"
        response = client.post(f"{self.settings.ollama_host}/api/chat", json=body)
        response.raise_for_status()
        data = response.json()
        if "message" in data and data["message"].get("content"):
            return data["message"]["content"]
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        raise RuntimeError("Ollama response missing content")

    def close(self) -> None:
        if self._http_client:
            self._http_client.close()
            self._http_client = None

    def __del__(self) -> None:  # pragma: no cover
        self.close()
