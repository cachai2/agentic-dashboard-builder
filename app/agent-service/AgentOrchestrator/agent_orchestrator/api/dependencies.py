from __future__ import annotations

from functools import lru_cache

from ..runtime.coordinator import SessionCoordinator
from ..runtime.persistence import PersistenceManager
from ..runtime.session_store import SessionStore


@lru_cache(maxsize=1)
def get_coordinator() -> SessionCoordinator:
    store = SessionStore()
    persistence = PersistenceManager()
    return SessionCoordinator(store, persistence=persistence)
