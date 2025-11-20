from __future__ import annotations

from typing import Any, Tuple

from storage_tool.config import get_storage_settings
from storage_tool.services.storage import ArtifactStorage


class PersistenceManager:
    """Bridges orchestrator workflows with the shared storage helper."""

    def __init__(self, storage: ArtifactStorage | None = None) -> None:
        self._storage = storage or ArtifactStorage(get_storage_settings())

    async def persist_dataset(self, session_id: str, filename: str, payload: bytes) -> Tuple[str, str]:
        blob_path = await self._storage.upload_dataset(session_id, filename, payload)
        sas_url = await self._storage.generate_dataset_read_url(blob_path, expiry_minutes=120)
        return blob_path, sas_url

    async def persist_results(self, session_id: str, payload: dict[str, Any]) -> Tuple[str, str]:
        blob_path = await self._storage.upload_results(session_id, payload)
        sas_url = await self._storage.generate_artifact_read_url(blob_path, expiry_minutes=720)
        return blob_path, sas_url

    async def persist_dashboard_html(self, session_id: str, html: str) -> Tuple[str, str]:
        blob_path = await self._storage.upload_dashboard(session_id, html)
        sas_url = await self._storage.generate_artifact_read_url(blob_path, expiry_minutes=720)
        return blob_path, sas_url

    async def persist_events(self, session_id: str, events: list[dict[str, Any]]) -> Tuple[str, str]:
        blob_path = await self._storage.upload_events(session_id, events)
        sas_url = await self._storage.generate_artifact_read_url(blob_path, expiry_minutes=720)
        return blob_path, sas_url

    async def download_dataset(self, blob_path: str) -> bytes:
        return await self._storage.download_dataset(blob_path)
