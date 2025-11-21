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

COPY ollama-proxy-service/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Preserve package name expected by imports (ollama_proxy_service)
COPY ollama-proxy-service/. ${APP_HOME}/ollama_proxy_service/
# Copy the shared dashboard schema used by the validator
COPY agent-service/schemas/ ${APP_HOME}/schemas/

ENV PYTHONPATH=${APP_HOME} \
    HOST=0.0.0.0 \
    PORT=8080

EXPOSE 8080

CMD ["uvicorn", "ollama_proxy_service.app.service:app", "--host", "0.0.0.0", "--port", "8080"]
