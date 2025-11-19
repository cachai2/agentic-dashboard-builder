"""Backward-compatible entrypoint that re-exports the compose tool CLI."""

from app.tools.compose_tool import app  # noqa: F401


if __name__ == "__main__":  # pragma: no cover
    app()
