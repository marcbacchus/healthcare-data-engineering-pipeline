# Phase 5 — containerizes the Streamlit agent UI for Azure Container Apps.
# Build from the repo root: docker build -f agent/Dockerfile -t healthcare-agent .
FROM python:3.13-slim

WORKDIR /app

# Secrets (Snowflake, Anthropic, OpenAI, Databricks) are injected as container
# env vars at run/deploy time — never baked into the image. See .dockerignore.
COPY agent/requirements.txt agent/requirements.txt
RUN pip install --no-cache-dir -r agent/requirements.txt

COPY agent/ agent/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "agent/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
