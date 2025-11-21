# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY agent-service/. ${APP_HOME}/
# Stage the Ollama proxy source alongside the orchestrator so its modules are importable at runtime
COPY ollama-proxy-service/. ${APP_HOME}/ollama_proxy_service/

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r CsvProfilerAgent/requirements.txt \
    && pip install --no-cache-dir -r ChartRenderingAgent/requirements.txt \
    && pip install --no-cache-dir -r ollama_proxy_service/requirements.txt \
    && pip install --no-cache-dir -e AgentOrchestrator

ENV PYTHONPATH=${APP_HOME}
ENV PORT=8080

EXPOSE 8080

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
