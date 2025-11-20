from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from urllib.parse import quote

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    generate_blob_sas,
)

from ..config import StorageSettings


@dataclass(slots=True)
class StoredArtifacts:
    dataset_blob_path: str
    results_blob_path: str | None = None
    wrangling_profile_blob_path: str | None = None
    wrangling_manifest_blob_path: str | None = None
    dashboard_blob_path: str | None = None


class ArtifactStorage:
    """Async helpers for persisting datasets, profiles, and dashboards."""

    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings
        self._account_key: str | None = None

        if settings.storage_connection_string:
            self._service_client = BlobServiceClient.from_connection_string(
                settings.storage_connection_string
            )
            self._account_key = self._extract_account_key(settings.storage_connection_string)
        else:
            account_url = f"https://{settings.storage_account_name}.blob.core.windows.net"
            credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
            self._service_client = BlobServiceClient(account_url=account_url, credential=credential)

        self._container_client = self._service_client.get_container_client(settings.storage_container_name)
        try:
            self._container_client.create_container()
        except ResourceExistsError:
            pass

    async def upload_dataset(self, run_id: str, filename: str, data: bytes) -> str:
        blob_path = f"{self._settings.raw_prefix}/{run_id}/{filename}"
        await asyncio.to_thread(self._upload_bytes, blob_path, data)
        return blob_path

    async def download_dataset(self, blob_path: str) -> bytes:
        return await asyncio.to_thread(self._download_bytes, blob_path)

    async def upload_results(self, run_id: str, payload: dict[str, Any]) -> str:
        blob_path = f"{self._settings.runs_prefix}/{run_id}/results.json"
        await asyncio.to_thread(self._upload_bytes, blob_path, payload)
        return blob_path

    async def upload_dashboard(self, run_id: str, html: str) -> str:
        blob_path = f"{self._settings.runs_prefix}/{run_id}/dashboard/index.html"
        await asyncio.to_thread(self._upload_bytes, blob_path, html)
        return blob_path

    async def download_results(self, run_id: str) -> dict[str, Any]:
        blob_path = f"{self._settings.runs_prefix}/{run_id}/results.json"
        data = await asyncio.to_thread(self._download_bytes, blob_path)
        return json.loads(data.decode("utf-8"))

    async def upload_wrangle_profile(self, run_id: str, payload: dict[str, Any]) -> str:
        blob_path = f"{self._settings.runs_prefix}/{run_id}/wrangler/profile.json"
        await asyncio.to_thread(self._upload_bytes, blob_path, payload)
        return blob_path

    async def upload_wrangle_manifest(self, run_id: str, payload: dict[str, Any]) -> str:
        blob_path = f"{self._settings.runs_prefix}/{run_id}/wrangler/manifest.json"
        await asyncio.to_thread(self._upload_bytes, blob_path, payload)
        return blob_path

    async def generate_artifact_read_url(self, blob_path: str, *, expiry_minutes: int = 30) -> str:
        return await asyncio.to_thread(self._generate_blob_read_url, blob_path, expiry_minutes)

    async def generate_dataset_read_url(self, blob_path: str, *, expiry_minutes: int = 30) -> str:
        return await self.generate_artifact_read_url(blob_path, expiry_minutes=expiry_minutes)

    def _upload_bytes(self, blob_path: str, data: bytes | dict[str, Any] | str) -> None:
        if isinstance(data, dict):
            stream = BytesIO()
            stream.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
            stream.seek(0)
            self._container_client.upload_blob(name=blob_path, data=stream, overwrite=True)
        elif isinstance(data, str):
            stream = BytesIO(data.encode("utf-8"))
            stream.seek(0)
            self._container_client.upload_blob(name=blob_path, data=stream, overwrite=True)
        else:
            self._container_client.upload_blob(name=blob_path, data=data, overwrite=True)

    def _download_bytes(self, blob_path: str) -> bytes:
        downloader = self._container_client.download_blob(blob_path)
        return downloader.readall()

    def _generate_blob_read_url(self, blob_path: str, expiry_minutes: int) -> str:
        start = datetime.now(timezone.utc) - timedelta(minutes=5)
        expiry = start + timedelta(minutes=expiry_minutes)

        if self._account_key:
            sas_token = generate_blob_sas(
                account_name=self._settings.storage_account_name,
                container_name=self._settings.storage_container_name,
                blob_name=blob_path,
                account_key=self._account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
                start=start,
            )
        else:
            delegation_key = self._service_client.get_user_delegation_key(
                key_start_time=start,
                key_expiry_time=expiry + timedelta(minutes=5),
            )
            sas_token = generate_blob_sas(
                account_name=self._settings.storage_account_name,
                container_name=self._settings.storage_container_name,
                blob_name=blob_path,
                user_delegation_key=delegation_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
                start=start,
            )

        encoded_blob_path = quote(blob_path, safe="/")
        return f"{self._blob_base_url}/{encoded_blob_path}?{sas_token}"

    @property
    def _blob_base_url(self) -> str:
        return (
            f"https://{self._settings.storage_account_name}.blob.core.windows.net/"
            f"{self._settings.storage_container_name}"
        )

    @staticmethod
    def _extract_account_key(connection_string: str) -> str | None:
        for part in connection_string.split(";"):
            if part.startswith("AccountKey="):
                return part.split("=", 1)[1]
        return None
