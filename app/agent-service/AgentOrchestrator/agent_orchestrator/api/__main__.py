from __future__ import annotations

import uvicorn


def main() -> None:  # pragma: no cover - CLI helper
    uvicorn.run("agent_orchestrator.api:app", host="0.0.0.0", port=8800, reload=False)


if __name__ == "__main__":  # pragma: no cover
    main()
