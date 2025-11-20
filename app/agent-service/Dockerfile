# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYGROUND_HOME=/app/Playground

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY . ${PLAYGROUND_HOME}

WORKDIR ${PLAYGROUND_HOME}

RUN mkdir -p /app/schemas \
    && cp -r CsvProfilerAgent/schemas/. /app/schemas \
    && rm -rf ${PLAYGROUND_HOME}/schemas \
    && ln -s /app/schemas ${PLAYGROUND_HOME}/schemas

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r CsvProfilerAgent/requirements.txt \
    && pip install --no-cache-dir -r ChartRenderingAgent/requirements.txt \
    && pip install --no-cache-dir -e AgentOrchestrator

ENV PYTHONPATH=/app

WORKDIR ${PLAYGROUND_HOME}/AgentOrchestrator

ENTRYPOINT ["python", "-m", "agent_orchestrator.cli"]
CMD ["--help"]
