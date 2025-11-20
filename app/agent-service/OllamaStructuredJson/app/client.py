"""Client wrapper for interacting with the Ollama HTTP API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import Settings, get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OllamaClient:
    """Simple HTTP/S client for Ollama chat completions."""

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
        response = self.chat(
            messages=[
                {"role": "system", "content": payload["system"]},
                {"role": "user", "content": payload["user"]},
            ],
            format_payload=schema_payload,
        )
        return self.extract_message_text(response)

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        format_payload: Optional[Dict[str, Any] | str] = None,
        model: Optional[str] = None,
        stream: bool = False,
        temperature: Optional[float] = None,
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        body: Dict[str, Any] = {
            "model": model or self.settings.ollama_model,
            "messages": messages,
            "stream": stream,
        }
        options = extra_options.copy() if extra_options else {}
        if temperature is not None:
            options.setdefault("temperature", temperature)
        if options:
            body["options"] = options
        if format_payload is not None:
            body["format"] = format_payload
        response = client.post(f"{self.settings.ollama_host}/api/chat", json=body)
        response.raise_for_status()
        return response.json()

    def _load_mock_plan(self) -> str:
        mock_path = PROJECT_ROOT / "samples" / "mock_plan.json"
        return mock_path.read_text(encoding="utf-8")

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        schema: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        stream: bool = False,
    ) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        response = self.chat(
            messages,
            format_payload=schema or "json",
            model=model,
            temperature=temperature,
            stream=stream,
        )
        raw = self.extract_message_text(response)
        parsed = json.loads(raw)
        return parsed, raw, response

    def chat_general(
        self,
        messages: List[Dict[str, str]],
        *,
        format_payload: Optional[Dict[str, Any] | str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        response = self.chat(
            messages,
            format_payload=format_payload,
            model=model,
            temperature=temperature,
            stream=stream,
        )
        content = self.extract_message_text(response)
        return content, response

    @staticmethod
    def extract_message_text(data: Dict[str, Any]) -> str:
        if "message" in data and data["message"].get("content"):
            return data["message"]["content"]
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"].get("content", "")
        raise RuntimeError("Ollama response missing content")

    def close(self) -> None:
        if self._http_client:
            self._http_client.close()
            self._http_client = None

    def __del__(self) -> None:  # pragma: no cover
        self.close()
