from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from .dependencies import get_coordinator
from .models import DashboardResponse, StatusResponse, UploadMetadata, UploadSession
from ..runtime.coordinator import DashboardNotReadyError, SessionCoordinator
from ..runtime.session_store import SessionNotFoundError

router = APIRouter()


@router.post("/upload", response_model=UploadSession, response_model_by_alias=True)
async def upload_csv(
    file: UploadFile = File(...),
    scenario_name: str = Form(..., alias="scenarioName"),
    objective: str = Form(...),
    notes: str | None = Form(default=None),
    coordinator: SessionCoordinator = Depends(get_coordinator),
) -> UploadSession:
    payload = await file.read()
    metadata = UploadMetadata(scenario_name=scenario_name, objective=objective, notes=notes or None)
    try:
        return await coordinator.handle_upload(filename=file.filename or "dataset.csv", payload=payload, metadata=metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/dashboard/status", response_model=StatusResponse, response_model_by_alias=True)
async def get_status(
    session_id: str = Query(..., alias="sessionId"),
    coordinator: SessionCoordinator = Depends(get_coordinator),
) -> StatusResponse:
    try:
        return await coordinator.get_status(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/dashboard/view", response_model=DashboardResponse, response_model_by_alias=True)
async def get_dashboard(
    session_id: str = Query(..., alias="sessionId"),
    coordinator: SessionCoordinator = Depends(get_coordinator),
) -> DashboardResponse:
    try:
        return await coordinator.get_dashboard(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except DashboardNotReadyError as exc:
        raise HTTPException(status_code=425, detail=str(exc)) from exc
