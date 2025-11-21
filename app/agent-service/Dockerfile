# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl

# Copy only the directories/files required at runtime to keep the context lean
COPY agent-service/AgentOrchestrator ${APP_HOME}/AgentOrchestrator
COPY agent-service/ChartRenderingAgent ${APP_HOME}/ChartRenderingAgent
COPY agent-service/CsvProfilerAgent ${APP_HOME}/CsvProfilerAgent
COPY agent-service/storage_tool ${APP_HOME}/storage_tool
COPY agent-service/schemas ${APP_HOME}/schemas
COPY agent-service/app ${APP_HOME}/app
COPY agent-service/docker-entrypoint.sh ${APP_HOME}/

# Stage the Ollama proxy source alongside the orchestrator so its modules are importable at runtime
COPY ollama-proxy-service/. ${APP_HOME}/ollama_proxy_service/

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && cat CsvProfilerAgent/requirements.txt ChartRenderingAgent/requirements.txt ollama_proxy_service/requirements.txt > /tmp/combined-requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/combined-requirements.txt \
    && rm /tmp/combined-requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir -e AgentOrchestrator \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR ${APP_HOME}

# Copy dependency layer and application source from the builder image
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder ${APP_HOME}/ ${APP_HOME}/

ENV PYTHONPATH=${APP_HOME}
ENV PORT=8080

EXPOSE 8080

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
