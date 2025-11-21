"""FastAPI application that fronts Ollama with simple JSON/general endpoints."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .client import OllamaClient
from .builder import render_prompt, compute_prompt_hash
from .config import get_settings
from .schemas import (
    ChatMessage,
    GeneralChatRequest,
    GeneralChatResponse,
    HealthResponse,
    JsonChatRequest,
    JsonChatResponse,
    PlanRequest,
    PlanResponse,
)
from .validator import PlanValidator

settings = get_settings()
client = OllamaClient(settings)
plan_validator = PlanValidator(settings)

app = FastAPI(title="Ollama Gateway", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_MAX_INVALID_SNIPPET_CHARS = 2000


def _compress_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _build_retry_user_prompt(base_prompt: str, invalid_output: str, failure_reason: str) -> str:
    snippet = (invalid_output or "").strip() or "<empty response>"
    if len(snippet) > _MAX_INVALID_SNIPPET_CHARS:
        snippet = f"{snippet[:_MAX_INVALID_SNIPPET_CHARS]}\n...truncated..."

    reason = _compress_whitespace(failure_reason) or "unknown error"
    if len(reason) > 300:
        reason = f"{reason[:300]}..."

    instructions = (
        "\n\nThe previous response failed because it did not produce valid DashboardPlan JSON ("
        f"{reason}). Carefully fix the invalid output shown between <BEGIN_INVALID_OUTPUT> and "
        "<END_INVALID_OUTPUT> so it matches the schema exactly. Respond with ONLY the corrected JSON "
        "object — no commentary or markdown.\n"
        "<BEGIN_INVALID_OUTPUT>\n"
        f"{snippet}\n"
        "<END_INVALID_OUTPUT>\n"
    )
    return base_prompt + instructions


@app.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", mode=settings.ollama_mode, model=settings.ollama_model)


@app.post("/json", response_model=JsonChatResponse)
def json_chat(request: JsonChatRequest) -> JsonChatResponse:
    try:
        parsed, raw, provider_response = client.chat_json(
            messages=_messages_to_payload(request.messages),
            schema=request.response_schema,
            model=request.model,
            stream=request.stream,
            temperature=request.temperature,
        )
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Model returned invalid JSON: {exc}") from exc
    return JsonChatResponse(
        content=parsed,
        raw=raw,
        model=provider_response.get("model", settings.ollama_model),
        provider_response=provider_response,
    )


@app.post("/plan", response_model=PlanResponse)
def plan_endpoint(request: PlanRequest) -> PlanResponse:
    prompt_bundle = render_prompt(request.profile_summary, prompt_version=request.prompt_version)
    base_prompt = prompt_bundle["user"]
    raw_response = ""
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            raw_response = client.generate_plan_text(prompt_bundle, response_schema=plan_validator.schema)
            plan = plan_validator.parse_and_validate(raw_response)
            metadata: Dict[str, Any] = {
                "prompt_version": request.prompt_version,
                "prompt_hash": prompt_bundle["prompt_hash"],
                "session_id": request.session_id,
                "round_trips": attempt + 1,
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }
            return PlanResponse(plan=plan, metadata=metadata, raw_response=raw_response)
        except Exception as exc:  # pragma: no cover - depends on upstream service
            last_error = exc
            if attempt == 0:
                prompt_bundle["user"] = _build_retry_user_prompt(base_prompt, raw_response, str(exc))
                prompt_bundle["prompt_hash"] = compute_prompt_hash(
                    prompt_bundle["system"], prompt_bundle["user"], prompt_bundle["prompt_version"]
                )
                continue
            raise HTTPException(status_code=502, detail="Planner failed after retries") from exc

    raise HTTPException(status_code=502, detail="Planner failed unexpectedly") from last_error


@app.post("/general", response_model=GeneralChatResponse)
def general_chat(request: GeneralChatRequest) -> GeneralChatResponse:
    content, provider_response = client.chat_general(
        messages=_messages_to_payload(request.messages),
        format_payload=request.format,
        model=request.model,
        stream=request.stream,
        temperature=request.temperature,
    )
    return GeneralChatResponse(
        content=content,
        model=provider_response.get("model", settings.ollama_model),
        provider_response=provider_response,
    )


def _messages_to_payload(messages: List[ChatMessage]) -> List[Dict[str, str]]:
    return [message.model_dump() for message in messages]
