# Dockerfile (repo root)
# Multi-stage build: builder stage installs dependencies (including heavy
# ML packages pulled in by sentence-transformers), final stage copies only
# the installed packages + app code, keeping the runtime image slim.
#
# Build context is the REPO ROOT, since main.py imports sibling modules
# (retrieval_engine.py, rag_chatbot.py, etc.) that live at the project
# root, not inside coverage-chatbot-api/. See docker-compose.yml.
#
# Note: unlike Day 28's docker-compose.yml (which volume-mounts chroma_data
# and coverage.db from the host), this image BAKES both in directly. That's
# a deliberate difference for the Kubernetes deployment: Day 29's manifests
# don't set up a PersistentVolume, so anything not baked into the image
# would silently start empty inside the pod (exactly what happened here --
# the vector DB was empty, degrading answer quality without an obvious
# error, since Chroma auto-creates an empty collection rather than failing).

# ---------- Builder stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY coverage-chatbot-api/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---------- Final stage ----------
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from the builder stage (not the build tools/cache)
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy root-level modules that main.py imports as siblings
COPY retrieval_engine.py rag_chatbot.py redact_pii.py guardrails_config.py token_utils.py ./
COPY coverage.db ./
COPY chroma_data/ ./chroma_data/

# Copy the backend app itself
COPY coverage-chatbot-api/main.py ./coverage-chatbot-api/main.py

WORKDIR /app/coverage-chatbot-api

EXPOSE 8000

# ---------- Health check ----------
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
