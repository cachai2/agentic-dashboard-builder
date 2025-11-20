"""Client wrapper for interacting with the Ollama HTTP API."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import Settings, get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


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
        endpoint, use_generate = self._build_endpoint()
        body = self._build_request_body(
            messages,
            format_payload=format_payload,
            model=model,
            stream=stream,
            temperature=temperature,
            extra_options=extra_options,
            use_generate=use_generate,
        )
        logger.debug(
            "Posting to %s (generate=%s) payload=%s",
            endpoint,
            use_generate,
            self._format_payload_for_log(body),
        )
        response = client.post(endpoint, json=body)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            logger.error(
                "Ollama request failed: status=%s endpoint=%s body=%s",
                response.status_code,
                endpoint,
                self._format_payload_for_log(body),
            )
            logger.error("Response text: %s", response.text[:800])
            raise
        return response.json()

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

    def _build_endpoint(self) -> Tuple[str, bool]:
        base = self.settings.ollama_host.rstrip("/")
        api_path = (self.settings.ollama_api_path or "").strip()
        if api_path:
            api_path = "/" + api_path.lstrip("/")
        endpoint = f"{base}{api_path}" if api_path else base
        return endpoint, endpoint.endswith("/generate")

    def _build_request_body(
        self,
        messages: List[Dict[str, str]],
        *,
        format_payload: Optional[Dict[str, Any] | str],
        model: Optional[str],
        stream: bool,
        temperature: Optional[float],
        extra_options: Optional[Dict[str, Any]],
        use_generate: bool,
    ) -> Dict[str, Any]:
        payload_model = model or self.settings.ollama_model
        options = extra_options.copy() if extra_options else {}
        if temperature is not None:
            options.setdefault("temperature", temperature)

        if use_generate:
            system_prompt, prompt = self._messages_to_prompt(messages)
            body: Dict[str, Any] = {
                "model": payload_model,
                "prompt": prompt or "",
                "stream": stream,
            }
            if system_prompt:
                body["system"] = system_prompt
        else:
            body = {
                "model": payload_model,
                "messages": messages,
                "stream": stream,
            }

        if format_payload is not None:
            options.setdefault("format", format_payload)
        if options:
            body["options"] = options
        return body

    @staticmethod
    def _messages_to_prompt(messages: List[Dict[str, str]]) -> Tuple[Optional[str], str]:
        system_prompt: Optional[str] = None
        prompt_parts: List[str] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system" and system_prompt is None:
                system_prompt = content
                continue
            prompt_parts.append(content)
        prompt = "\n\n".join(part.strip() for part in prompt_parts if part.strip())
        return system_prompt, prompt

    @staticmethod
    def _format_payload_for_log(payload: Dict[str, Any]) -> str:
        try:
            serialized = json.dumps(payload)
        except Exception:  # pragma: no cover - best effort logging
            return str(payload)
        return serialized[:800]

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
