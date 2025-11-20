"""FastAPI application that fronts Ollama with simple JSON/general endpoints."""

from __future__ import annotations

import json
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .client import OllamaClient
from .config import get_settings
from .schemas import (
    ChatMessage,
    GeneralChatRequest,
    GeneralChatResponse,
    HealthResponse,
    JsonChatRequest,
    JsonChatResponse,
)

settings = get_settings()
client = OllamaClient(settings)

app = FastAPI(title="Ollama Gateway", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", mode=settings.ollama_mode, model=settings.ollama_model)


@app.post("/json", response_model=JsonChatResponse)
def json_chat(request: JsonChatRequest) -> JsonChatResponse:
    format_payload = request.schema or "json"
    response = client.chat(
        messages=_messages_to_payload(request.messages),
        format_payload=format_payload,
        model=request.model,
        stream=request.stream,
        temperature=request.temperature,
    )
    raw = client.extract_message_text(response)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - only triggered on invalid LLM output
        raise HTTPException(status_code=502, detail=f"Model returned invalid JSON: {exc}") from exc
    return JsonChatResponse(content=parsed, raw=raw, model=response.get("model", settings.ollama_model), provider_response=response)


@app.post("/general", response_model=GeneralChatResponse)
def general_chat(request: GeneralChatRequest) -> GeneralChatResponse:
    response = client.chat(
        messages=_messages_to_payload(request.messages),
        format_payload=request.format,
        model=request.model,
        stream=request.stream,
        temperature=request.temperature,
    )
    content = client.extract_message_text(response)
    return GeneralChatResponse(content=content, model=response.get("model", settings.ollama_model), provider_response=response)


def _messages_to_payload(messages: List[ChatMessage]) -> List[Dict[str, str]]:
    return [message.model_dump() for message in messages]
