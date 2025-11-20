from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(slots=True)
class StorageSettings:
    """Configuration used by the artifact storage helpers."""

    storage_account_name: str
    storage_container_name: str
    storage_connection_string: str | None
    raw_prefix: str
    runs_prefix: str

    @classmethod
    def from_env(cls) -> "StorageSettings":
        account_name = (
            os.getenv("AGENT_STORAGE_ACCOUNT_NAME")
            or os.getenv("STORAGE_ACCOUNT_NAME")
            or os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        )
        if not account_name:
            raise RuntimeError(
                "AGENT_STORAGE_ACCOUNT_NAME is not configured. "
                "Use azd env refresh or set the variable manually."
            )

        container_name = os.getenv("AGENT_STORAGE_CONTAINER_NAME", "agent-artifacts")
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        raw_prefix = os.getenv("AGENT_STORAGE_RAW_PREFIX", "raw")
        runs_prefix = os.getenv("AGENT_STORAGE_RUN_PREFIX", "runs")

        return cls(
            storage_account_name=account_name,
            storage_container_name=container_name,
            storage_connection_string=connection_string,
            raw_prefix=raw_prefix,
            runs_prefix=runs_prefix,
        )


@lru_cache(maxsize=1)
def get_storage_settings() -> StorageSettings:
    return StorageSettings.from_env()
