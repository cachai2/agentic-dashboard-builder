#!/bin/sh
set -e

# Allow custom commands to override the default uvicorn startup.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

APP_MODULE="${APP_MODULE:-agent_orchestrator.api.app:app}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

exec uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
