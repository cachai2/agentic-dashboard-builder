from __future__ import annotations

import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .builder import compute_prompt_hash, render_prompt
from .client import OllamaClient
from .config import get_settings
from .schemas import HealthResponse, PlanMetadata, PlanRequest, PlanResponse
from .validator import PlanValidator

settings = get_settings()
client = OllamaClient(settings)
validator = PlanValidator(settings)

_MAX_INVALID_SNIPPET_CHARS = 4000

app = FastAPI(title="Ollama Structured JSON Agent", version="0.1.0")
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


@app.post("/plan", response_model=PlanResponse)
def plan(request: PlanRequest) -> PlanResponse:
    prompt_bundle = render_prompt(request.profile_summary, request.prompt_version)
    base_user_prompt = prompt_bundle["user"]
    start = perf_counter()
    attempts = 0
    last_error: Exception | None = None

    for attempt in range(2):
        attempts = attempt + 1
        raw_response = ""
        try:
            raw_response = client.generate_plan_text(prompt_bundle, validator.schema)
            plan = validator.parse_and_validate(raw_response)
            metadata = PlanMetadata(
                prompt_version=request.prompt_version,
                model=settings.ollama_model,
                round_trips=attempts,
                duration_ms=(perf_counter() - start) * 1000,
                prompt_hash=prompt_bundle["prompt_hash"],
                requested_at=datetime.now(timezone.utc),
            )
            return PlanResponse(plan=plan, metadata=metadata)
        except Exception as exc:  # broad catch to surface error detail upstream
            last_error = exc
            # For retry #2, append a clarification to the user prompt to enforce JSON output.
            if attempt == 0:
                prompt_bundle["user"] = _build_retry_user_prompt(
                    base_user_prompt,
                    raw_response,
                    str(exc),
                )
                prompt_bundle["prompt_hash"] = compute_prompt_hash(
                    prompt_bundle["system"],
                    prompt_bundle["user"],
                    prompt_bundle["prompt_version"],
                )

    raise HTTPException(status_code=502, detail=str(last_error))


def _build_retry_user_prompt(base_prompt: str, invalid_output: str, failure_reason: str) -> str:
    snippet = (invalid_output or "").strip()
    if not snippet:
        snippet = "<empty response>"
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


def _compress_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
