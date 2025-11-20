# CSV Storage Tool Reference

Use this guide to recreate the CSV storage/persistence layer from the `ignite-25-codex` agent service inside any other project. It includes the exact Python modules, package dependencies, required environment variables, and the Azure infrastructure snippets you need.

---

## 1. Prerequisites

### Runtime dependencies

Install the same Azure SDK packages used by the tool:

```bash
pip install azure-storage-blob==12.19.1 azure-identity==1.17.1
```

### Environment variables

Set the following variables (in your container app, local `.env`, or CI definition):

| Variable | Purpose |
| --- | --- |
| `AGENT_STORAGE_ACCOUNT_NAME` | Azure Storage account name hosting the artifacts container |
| `AGENT_STORAGE_CONTAINER_NAME` (default `agent-artifacts`) | Blob container name |
| `AGENT_STORAGE_RAW_PREFIX` (default `raw`) | Prefix for uploaded datasets |
| `AGENT_STORAGE_RUN_PREFIX` (default `runs`) | Prefix for run results, dashboards, diagnostics |
| `AZURE_STORAGE_CONNECTION_STRING` (optional) | Use when you prefer connection-string auth instead of Managed Identity |

When running in Azure Container Apps with a system-assigned identity, you can omit the connection string. The SDK will pick up the identity automatically.

---

## 2. Settings shim (`config.py`)

Create `app/config.py` to centralize settings used by the storage layer. You can copy this verbatim:

```python
from __future__ import annotations

from dataclasses import dataclass
import os
from functools import lru_cache


@dataclass(slots=True)
class Settings:
    storage_account_name: str
    storage_container_name: str
    storage_connection_string: str | None
    raw_prefix: str
    runs_prefix: str

    @classmethod
    def from_env(cls) -> "Settings":
        storage_account = (
            os.getenv("AGENT_STORAGE_ACCOUNT_NAME")
            or os.getenv("STORAGE_ACCOUNT_NAME")
            or os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        )
        if not storage_account:
            raise RuntimeError(
                "AGENT_STORAGE_ACCOUNT_NAME is not configured. "
                "Update infrastructure or set the environment variable."
            )

        container_name = os.getenv("AGENT_STORAGE_CONTAINER_NAME", "agent-artifacts")
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        raw_prefix = os.getenv("AGENT_STORAGE_RAW_PREFIX", "raw")
        runs_prefix = os.getenv("AGENT_STORAGE_RUN_PREFIX", "runs")

        return cls(
            storage_account_name=storage_account,
            storage_container_name=container_name,
            storage_connection_string=connection_string,
            raw_prefix=raw_prefix,
            runs_prefix=runs_prefix,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
```

If your project already has a settings object, merge these fields into it instead of creating a duplicate dataclass.

---

## 3. Blob helper (`services/storage.py`)

Add the storage service under `app/services/storage.py`:

```python
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

from ..config import Settings


@dataclass(slots=True)
class StoredArtifacts:
    dataset_blob_path: str
    results_blob_path: str | None = None
    wrangling_profile_blob_path: str | None = None
    wrangling_manifest_blob_path: str | None = None
    dashboard_blob_path: str | None = None


class ArtifactStorage:
    def __init__(self, settings: Settings) -> None:
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

    async def generate_dataset_read_url(self, blob_path: str, *, expiry_minutes: int = 30) -> str:
        return await self.generate_artifact_read_url(blob_path, expiry_minutes=expiry_minutes)

    async def generate_artifact_read_url(self, blob_path: str, *, expiry_minutes: int = 30) -> str:
        return await asyncio.to_thread(self._generate_blob_read_url, blob_path, expiry_minutes)

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
```

Feel free to prune methods you do not need (for example, wrangling helpers) if your scenario is simpler.

---

## 4. Tool wrapper (`tools/storage_tool.py`)

Drop the tool facade under `app/tools/storage_tool.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models.workflow import AnalyzeCsvRequest
from ..services.pipeline import PipelineResult
from ..services.storage import ArtifactStorage


@dataclass(slots=True)
class PersistenceResult:
    results_blob_path: str
    dashboard_blob_path: Optional[str] = None
    dashboard_url: Optional[str] = None
    dashboard_mode: Optional[str] = None


class CsvStorageTool:
    def __init__(self, storage: ArtifactStorage) -> None:
        self._storage = storage

    async def load_dataset(self, request: AnalyzeCsvRequest) -> bytes:
        return await self._storage.download_dataset(request.dataset_blob_path)

    async def persist_results(
        self,
        request: AnalyzeCsvRequest,
        pipeline_result: PipelineResult,
    ) -> PersistenceResult:
        dashboard_blob: str | None = None
        dashboard_url: str | None = None
        dashboard_mode = pipeline_result.results.dashboard_mode

        if pipeline_result.dashboard_html and dashboard_mode is None:
            dashboard_mode = "fallback-curated"

        if pipeline_result.dashboard_html:
            dashboard_blob = await self._storage.upload_dashboard(
                request.run_id,
                pipeline_result.dashboard_html,
            )
            dashboard_url = await self._storage.generate_artifact_read_url(
                dashboard_blob,
                expiry_minutes=720,
            )
            pipeline_result.results.dashboard_url = dashboard_url
            diagnostics_payload = pipeline_result.results.diagnostics or {}
            if "dashboard" not in diagnostics_payload:
                diagnostics_payload = dict(diagnostics_payload)
            dashboard_details = dict(diagnostics_payload.get("dashboard") or {})
            dashboard_details.update(
                {
                    "blob_path": dashboard_blob,
                    "mode": dashboard_mode,
                }
            )
            diagnostics_payload["dashboard"] = dashboard_details
            pipeline_result.results.diagnostics = diagnostics_payload
            pipeline_result.diagnostics.setdefault("dashboard", {})
            pipeline_result.diagnostics["dashboard"].update(
                {
                    "blob_path": dashboard_blob,
                    "url": dashboard_url,
                    "mode": dashboard_mode,
                }
            )

        pipeline_result.results.dashboard_mode = dashboard_mode
        results_payload = pipeline_result.results.model_dump()
        results_blob = await self._storage.upload_results(request.run_id, results_payload)
        return PersistenceResult(
            results_blob_path=results_blob,
            dashboard_blob_path=dashboard_blob,
            dashboard_url=dashboard_url,
            dashboard_mode=dashboard_mode,
        )

    async def download_results(self, run_id: str) -> dict[str, object]:
        return await self._storage.download_results(run_id)
```

`AnalyzeCsvRequest` and `PipelineResult` are thin Pydantic/dataclass models in the original project. If your shapes differ, adjust the tool accordingly—the storage logic stays the same.

---

## 5. Wiring it up

Inside your FastAPI / agent service startup, instantiate the storage service and tool once (for example, with FastAPI lifespan events):

```python
from fastapi import FastAPI

from app.config import get_settings
from app.services.storage import ArtifactStorage
from app.tools.storage_tool import CsvStorageTool

app = FastAPI()

@app.on_event("startup")
async def startup() -> None:
    settings = get_settings()
    app.state.storage = ArtifactStorage(settings)
    app.state.storage_tool = CsvStorageTool(app.state.storage)
```

Inject `app.state.storage_tool` wherever you run your analysis pipeline. Use `load_dataset` to fetch the CSV bytes and `persist_results` once the pipeline finishes.

---

## 6. Azure infrastructure snippets

### Storage account + container

Create the artifacts account/container using Bicep (trimmed from the main template):

```bicep
param location string
param storageAccountName string
param containerName string = 'agent-artifacts'

resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource artifactContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${storage.name}/default/${containerName}'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [storage]
}
```

### Container Apps environment variables

When defining your agent container app, inject the env vars so the Python code can locate the storage account:

```bicep
var agentServiceEnv = [
  {
    name: 'AGENT_STORAGE_ACCOUNT_NAME'
    value: storageAccountName
  }
  {
    name: 'AGENT_STORAGE_CONTAINER_NAME'
    value: containerName
  }
  {
    name: 'AGENT_STORAGE_RAW_PREFIX'
    value: 'raw'
  }
  {
    name: 'AGENT_STORAGE_RUN_PREFIX'
    value: 'runs'
  }
]

module agentService './modules/container-app.bicep' = {
  name: 'agentService'
  params: {
    name: agentServiceName
    environmentId: managedEnvironment.id
    workloadProfileName: 'consumption'
    containerSpec: {
      name: 'agent-service'
      image: '<your acr>/agent-service:latest'
      env: agentServiceEnv
      resources: {
        cpu: 1
        memory: '2Gi'
      }
    }
    ingressEnabled: true
    ingressExternal: false
    identity: {
      type: 'SystemAssigned'
    }
  }
}
```

Grant the container app’s managed identity `Storage Blob Data Contributor` on the storage account so it can upload/download blobs:

```bicep
resource agentStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, agentService.outputs.principalId, 'storage-blob-contrib')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'  // Storage Blob Data Contributor
    )
    principalId: agentService.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}
```

If you prefer connection-string auth (not recommended for production), generate the string during deployment and inject it as `AZURE_STORAGE_CONNECTION_STRING` instead of granting the role assignment.

---

## 7. Verification checklist

1. Deploy storage account + container and role assignment.
2. Confirm `AGENT_STORAGE_*` variables are present on the container app.
3. Ensure the Python image includes `azure-storage-blob` and `azure-identity`.
4. Hit your pipeline endpoint: it should upload datasets to `raw/<run-id>/` and persist results/dashboards under `runs/<run-id>/`.
5. (Optional) Validate the SAS URLs produced by `generate_artifact_read_url` open successfully for the configured expiry period.

With these pieces in place you can drop the storage tool into any other project and keep the CSV artifacts workflow identical to the Ignite demo.
