"""Tool wrapper around the CSV profiler agent."""

from __future__ import annotations

import logging
import sys
from importlib import import_module
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from ..settings import get_settings

try:  # pragma: no cover - fallback when Agent Framework isn't installed yet
    from agent_framework import ai_function
except ImportError:  # pragma: no cover
    def ai_function(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(func: Any) -> Any:
            return func

        return decorator

def _get_agent_service_root() -> Optional[Path]:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "agent-service":
            return parent
    return None


def _maybe_add_agent_service_root_to_sys_path() -> None:
    """Ensure the agent-service directory (which hosts CsvProfilerAgent) is importable."""

    agent_service_root = _get_agent_service_root()
    if agent_service_root is None or not (agent_service_root / "CsvProfilerAgent").exists():
        return

    agent_service_root_str = str(agent_service_root)
    if agent_service_root_str not in sys.path:
        sys.path.insert(0, agent_service_root_str)


def _load_local_profiling_module_from_source():
    """Load CsvProfilerAgent directly from the repository without touching sys.path."""

    agent_service_root = _get_agent_service_root()
    if agent_service_root is None:
        return None

    profiling_file = agent_service_root / "CsvProfilerAgent" / "app" / "profiling.py"
    if not profiling_file.exists():
        return None

    spec = importlib_util.spec_from_file_location("csv_profiler_local", profiling_file)
    if spec is None or spec.loader is None:
        return None

    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_profiling_module():
    """Load the profiling module from the local package or Playground fallback."""

    module_name = "CsvProfilerAgent.app.profiling"
    try:
        return import_module(module_name)
    except ModuleNotFoundError:
        _maybe_add_agent_service_root_to_sys_path()
        try:
            return import_module(module_name)
        except ModuleNotFoundError:
            local_module = _load_local_profiling_module_from_source()
            if local_module is not None:
                return local_module
            try:
                return import_module("Playground.CsvProfilerAgent.app.profiling")
            except ModuleNotFoundError as exc:
                raise ModuleNotFoundError(
                    "CsvProfilerAgent package not found. Ensure app/agent-service is on PYTHONPATH or install the package."
                ) from exc


_profiling_module = _load_profiling_module()
ProfilingOptions = _profiling_module.ProfilingOptions
profile_csv_path = _profiling_module.profile_csv_path

logger = logging.getLogger(__name__)


def _profile_via_http(csv_path: Path, dataset_name: Optional[str], max_rows: Optional[int]) -> Dict[str, Any]:
    settings = get_settings()
    assert settings.csv_profiler_endpoint is not None

    params = {}
    if dataset_name:
        params["dataset_name"] = dataset_name
    if max_rows is not None:
        params["max_rows"] = str(max_rows)

    logger.info("Posting CSV to profiler endpoint", extra={"endpoint": str(settings.csv_profiler_endpoint)})
    headers = {"Content-Type": "text/csv"}
    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            str(settings.csv_profiler_endpoint),
            params=params,
            content=csv_path.read_bytes(),
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


def _profile_locally(csv_path: Path, dataset_name: Optional[str], max_rows: Optional[int]) -> Dict[str, Any]:
    options = ProfilingOptions(max_rows=max_rows)
    profile = profile_csv_path(csv_path, dataset_name=dataset_name, options=options)
    return profile.model_dump(mode="json")


@ai_function(
    name="profile_dataset",
    description=(
        "Profile a CSV dataset and return the deterministic profiling JSON contract that feeds the planner."
    ),
)
def profile_dataset(
    csv_path: str,
    dataset_name: Optional[str] = None,
    max_rows: Optional[int] = None,
) -> Dict[str, Any]:
    """Profile the provided CSV path via HTTP (if configured) or the local profiling module."""

    path = Path(csv_path).expanduser().resolve()
    if not path.exists():  # pragma: no cover - defensive branch
        raise FileNotFoundError(f"CSV not found: {path}")

    settings = get_settings()
    effective_max_rows = max_rows if max_rows is not None else settings.csv_profiler_max_rows

    if settings.csv_profiler_endpoint:
        profile = _profile_via_http(path, dataset_name, effective_max_rows)
    else:
        profile = _profile_locally(path, dataset_name, effective_max_rows)

    logger.info(
        "Profiled dataset",
        extra={
            "dataset_name": dataset_name or path.stem,
            "rows": profile.get("row_count"),
            "columns": profile.get("column_count"),
            "max_rows": effective_max_rows,
        },
    )
    return profile
