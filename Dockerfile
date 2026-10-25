# Samanvay — demo web app (FastAPI + static page).
#
# Works for both deploy targets in DEPLOY.md:
#   - Hugging Face Spaces (Docker SDK): runs as user ID 1000, listens on 7860
#   - Nebius Serverless Endpoints: --container-port 7860
#
# Secrets: NONE are in this image. .env is excluded by .dockerignore, and
# NEBIUS_API_KEY must be provided at runtime as a platform secret (HF Space
# secret / Nebius SecretStash via --env-secret). Without it the app still
# starts; /api/health reports ready=false unless MEDBOT_MOCK_LLM=1.
#
# Retrieval indexes (rag/index/) are built at startup by api/app.py, so they
# always match the runtime EMBED_BACKEND.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Hugging Face Spaces runs the container as user ID 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

COPY --chown=user requirements.txt constraints.txt ./
RUN pip install --user -r requirements.txt -c constraints.txt

COPY --chown=user . .

# Safe defaults; override at runtime. Live calls need NEBIUS_API_KEY (secret).
ENV PORT=7860 \
    EMBED_BACKEND=tfidf \
    MEDBOT_MOCK_LLM=0

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"7860\")}/api/health', timeout=4)" || exit 1

CMD ["sh", "-c", "exec uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
