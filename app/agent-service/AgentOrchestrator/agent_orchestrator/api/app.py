from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router


def _get_allowed_origins() -> list[str]:
    raw_origins = os.getenv("ORCH_ALLOWED_ORIGINS")
    if raw_origins:
        return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return [
        "https://frontend-ignite-demo-evdeo.salmondune-d5fce79f.westus.azurecontainerapps.io",
        "http://localhost:5173",
    ]


def create_app() -> FastAPI:
    app = FastAPI(title="Ignite Agent Orchestrator", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
