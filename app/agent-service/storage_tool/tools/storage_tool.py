from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..services.storage import ArtifactStorage


@dataclass(slots=True)
class PersistenceResult:
    results_blob_path: str
    dashboard_blob_path: str | None = None
    dashboard_url: str | None = None
    dashboard_mode: str | None = None


class CsvStorageTool:
    """Facade that bridges pipeline objects with the ArtifactStorage helper."""

    def __init__(self, storage: ArtifactStorage) -> None:
        self._storage = storage

    async def load_dataset(self, dataset_blob_path: str) -> bytes:
        return await self._storage.download_dataset(dataset_blob_path)

    async def persist_results(
        self,
        run_id: str,
        pipeline_result: Any,
        *,
        expiry_minutes: int = 720,
    ) -> PersistenceResult:
        dashboard_blob: str | None = None
        dashboard_url: str | None = None
        results = getattr(pipeline_result, "results", None)
        if results is None:
            raise ValueError("pipeline_result.results is required")

        dashboard_mode = getattr(results, "dashboard_mode", None)
        dashboard_html = getattr(pipeline_result, "dashboard_html", None)

        if dashboard_html and dashboard_mode is None:
            dashboard_mode = "fallback-curated"

        if dashboard_html:
            dashboard_blob = await self._storage.upload_dashboard(run_id, dashboard_html)
            dashboard_url = await self._storage.generate_artifact_read_url(
                dashboard_blob,
                expiry_minutes=expiry_minutes,
            )

            if hasattr(results, "dashboard_url"):
                setattr(results, "dashboard_url", dashboard_url)

            diagnostics_payload = self._copy_dict(getattr(results, "diagnostics", None))
            dashboard_details = self._copy_dict(diagnostics_payload.get("dashboard"))
            dashboard_details.update(
                {
                    "blob_path": dashboard_blob,
                    "mode": dashboard_mode,
                }
            )
            diagnostics_payload["dashboard"] = dashboard_details
            if hasattr(results, "diagnostics"):
                setattr(results, "diagnostics", diagnostics_payload)

            root_diagnostics = self._copy_dict(getattr(pipeline_result, "diagnostics", None))
            nested_dashboard = self._copy_dict(root_diagnostics.get("dashboard"))
            nested_dashboard.update(
                {
                    "blob_path": dashboard_blob,
                    "url": dashboard_url,
                    "mode": dashboard_mode,
                }
            )
            root_diagnostics["dashboard"] = nested_dashboard
            if hasattr(pipeline_result, "diagnostics"):
                setattr(pipeline_result, "diagnostics", root_diagnostics)

        if hasattr(results, "dashboard_mode"):
            setattr(results, "dashboard_mode", dashboard_mode)

        results_payload = self._serialize_results(results)
        results_blob = await self._storage.upload_results(run_id, results_payload)
        return PersistenceResult(
            results_blob_path=results_blob,
            dashboard_blob_path=dashboard_blob,
            dashboard_url=dashboard_url,
            dashboard_mode=dashboard_mode,
        )

    async def download_results(self, run_id: str) -> dict[str, Any]:
        return await self._storage.download_results(run_id)

    @staticmethod
    def _copy_dict(candidate: Any) -> dict[str, Any]:
        if isinstance(candidate, dict):
            return dict(candidate)
        if candidate is None:
            return {}
        return dict(candidate)

    @staticmethod
    def _serialize_results(results: Any) -> dict[str, Any]:
        if hasattr(results, "model_dump"):
            return results.model_dump()
        if hasattr(results, "dict"):
            return results.dict()
        if isinstance(results, dict):
            return results
        raise TypeError("pipeline_result.results must be a dict or expose model_dump()")
