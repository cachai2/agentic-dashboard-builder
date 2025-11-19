"""Adapter registry for chart generation experiments."""
from __future__ import annotations

from typing import Dict, Type

from .base import BaseAdapter
from .plotly_express_adapter import PlotlyExpressAdapter
from .autoviz_adapter import AutoVizAdapter
from .deepchecks_adapter import DeepchecksAdapter

_ADAPTERS: Dict[str, Type[BaseAdapter]] = {
    PlotlyExpressAdapter.name: PlotlyExpressAdapter,
    AutoVizAdapter.name: AutoVizAdapter,
    DeepchecksAdapter.name: DeepchecksAdapter,
}


def get_registered_adapters() -> Dict[str, Type[BaseAdapter]]:
    """Return a copy of the adapter registry."""
    return dict(_ADAPTERS)


def resolve_adapter(name: str) -> Type[BaseAdapter]:
    """Resolve an adapter class by name."""
    key = name.lower()
    if key not in _ADAPTERS:
        available = ", ".join(sorted(_ADAPTERS))
        raise KeyError(f"Unknown adapter '{name}'. Available adapters: {available}")
    return _ADAPTERS[key]
