"""Pydantic schemas shared by the Ollama planner service."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str
    model: str


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class JsonChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional JSON schema passed to the Ollama format parameter.",
    )
    model: Optional[str] = Field(default=None, description="Override the default Ollama model.")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    stream: bool = Field(default=False, description="Forward streaming responses (currently always false).")


class JsonChatResponse(BaseModel):
    content: Dict[str, Any]
    raw: str
    model: str
    provider_response: Dict[str, Any]


class GeneralChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    model: Optional[str] = None
    format: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="Optional Ollama format payload (string or JSON schema).",
    )
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stream: bool = False


class GeneralChatResponse(BaseModel):
    content: str
    model: str
    provider_response: Dict[str, Any]
