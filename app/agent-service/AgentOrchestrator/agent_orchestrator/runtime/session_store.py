from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AgentStepSnapshot, DashboardArtifacts, SessionRecord, UploadMetadataPayload


class SessionNotFoundError(KeyError):
    """Raised when callers reference an unknown session identifier."""


class SessionStore:
    """In-memory registry for uploaded datasets and orchestration state."""

    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, *, metadata: UploadMetadataPayload, filename: str) -> SessionRecord:
        async with self._lock:
            session_id = uuid.uuid4().hex
            record = SessionRecord(
                session_id=session_id,
                uploaded_at=datetime.now(timezone.utc),
                original_filename=filename,
                metadata=metadata,
            )
            record.status_entries.append(
                AgentStepSnapshot(
                    id="upload",
                    tool_name="UploadHandler",
                    reasoning="Dataset accepted",
                    state="success",
                    started_at=record.uploaded_at,
                    finished_at=record.uploaded_at,
                )
            )
            self._records[session_id] = record
            return record

    async def attach_dataset_paths(
        self,
        session_id: str,
        *,
        local_path: Path | None = None,
        blob_path: str | None = None,
        dataset_url: str | None = None,
    ) -> SessionRecord:
        async with self._lock:
            record = self._get_locked(session_id)
            if local_path is not None:
                record.dataset_local_path = local_path
            if blob_path is not None:
                record.dataset_blob_path = blob_path
            if dataset_url is not None:
                record.dataset_url = dataset_url
            return record

    async def save_dashboard(
        self,
        session_id: str,
        dashboard: DashboardArtifacts,
        *,
        dashboard_blob_path: str | None = None,
        dashboard_url: str | None = None,
    ) -> SessionRecord:
        async with self._lock:
            record = self._get_locked(session_id)
            record.dashboard = dashboard
            record.is_complete = True
            if dashboard_blob_path is not None:
                record.dashboard_blob_path = dashboard_blob_path
            record.dashboard_url = dashboard_url or dashboard.iframe_url
            return record

    async def record_results(
        self,
        session_id: str,
        *,
        results_blob_path: str,
        results_url: str | None = None,
    ) -> SessionRecord:
        async with self._lock:
            record = self._get_locked(session_id)
            record.results_blob_path = results_blob_path
            record.results_url = results_url
            return record

    async def record_events(
        self,
        session_id: str,
        *,
        events: list[dict[str, Any]],
        events_blob_path: str | None = None,
        events_url: str | None = None,
    ) -> SessionRecord:
        async with self._lock:
            record = self._get_locked(session_id)
            record.events = events
            if events_blob_path is not None:
                record.events_blob_path = events_blob_path
            if events_url is not None:
                record.events_url = events_url
            return record

    async def upsert_status(self, session_id: str, snapshot: AgentStepSnapshot) -> SessionRecord:
        async with self._lock:
            record = self._get_locked(session_id)
            for idx, entry in enumerate(record.status_entries):
                if entry.id == snapshot.id:
                    record.status_entries[idx] = snapshot
                    break
            else:
                record.status_entries.append(snapshot)
            return record

    async def get(self, session_id: str) -> SessionRecord:
        async with self._lock:
            return self._get_locked(session_id)

    def _get_locked(self, session_id: str) -> SessionRecord:
        try:
            return self._records[session_id]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise SessionNotFoundError(session_id) from exc
