# Docker Notes — Day 28

## Setup

- **Backend:** `coverage-chatbot-api/Dockerfile`, multi-stage build. Builder stage installs dependencies (`fastapi`, `uvicorn`, `sentence-transformers`, `chromadb`, `guardrails-ai`, etc. — including `torch`, pulled in transitively) into a user site-packages directory; final stage copies only the installed packages plus the app code, keeping the runtime image slim (no build tools, no pip cache).
- **Frontend:** `Dockerfile.frontend` at repo root, also multi-stage. Kept in a separate image from the backend so it doesn't drag in `torch`/`chromadb`/`sentence-transformers` — it only needs `streamlit`, `pandas`, `requests`, and `pydantic`.
- **Build context:** both Dockerfiles build from the **repo root** as context (not their own folder), since `main.py` imports sibling modules (`retrieval_engine.py`, `rag_chatbot.py`, `redact_pii.py`, `guardrails_config.py`, `token_utils.py`) that live at the project root, not inside `coverage-chatbot-api/`.

## Two real gotchas found and fixed before the first successful build

1. **`app.py`'s `API_URL` was hardcoded to `http://localhost:8000`.** Inside Docker's network, the frontend container's "localhost" is itself, not the backend container — they're separate network namespaces. Fixed by making it read from an environment variable (`os.environ.get("API_URL", "http://localhost:8000")`), with `docker-compose.yml` overriding it to `http://backend:8000` (Docker's internal DNS resolves service names to the right container).

2. **`rag_chatbot.py`'s Ollama `base_url` was hardcoded to `http://localhost:11434/v1`.** Ollama runs on the **host Mac**, not inside any container — from inside the backend container, "localhost" means the container itself, which has no Ollama server running on it at all. Fixed the same way (environment variable, defaulting to the same local value for non-Docker dev), with `.env` setting it to `http://host.docker.internal:11434/v1` — Docker's special hostname for reaching services on the host machine.

Both of these would have caused confusing, silent-looking failures (connection refused, or the frontend just hanging) rather than an obvious error message, so catching them before the first build attempt saved real debugging time.

## docker-compose.yml wiring

- `backend` and `frontend` services, `frontend` depends on `backend`.
- **Volumes:** `./chroma_data:/app/chroma_data` and `./coverage.db:/app/coverage.db` — mounted rather than baked into the image, so vector data and conversation/usage history persist across container rebuilds instead of resetting to a frozen snapshot every time.
- **`env_file: .env`** on the backend service — `OLLAMA_BASE_URL` (and any future secrets) are never hardcoded or baked into the image; `.env` itself is gitignored, only `.env.example` (placeholder values) is committed.
- **`extra_hosts: host.docker.internal:host-gateway`** — required on Linux Docker; a harmless no-op on Docker Desktop for Mac, where `host.docker.internal` already resolves correctly by default (confirmed working without needing this line, but kept for portability).

## Build results

```
docker compose up --build
```

Both images built successfully:
- `dailytask-backend`: ~262s total build time (dominated by installing `torch`/`sentence-transformers`, expected for a from-scratch dependency install)
- `dailytask-frontend`: builds in parallel, much faster (~12s for its own dependency install, since it avoids the heavy ML packages)

Both containers started cleanly with no errors:
```
frontend-1  | Uvicorn server started on 0.0.0.0:8501
backend-1   | Application startup complete.
backend-1   | Uvicorn running on http://0.0.0.0:8000
```

## Step 5: /health confirmed from inside and outside the container network

**From the host machine:**
```
curl http://localhost:8000/health
{"status":"ok"}
```

**From inside the container network:** the backend's own log line confirms the Docker `HEALTHCHECK` instruction successfully calling `/health` internally:
```
backend-1   | INFO:     127.0.0.1:59000 - "GET /health HTTP/1.1" 200 OK
```

## Step 6: HEALTHCHECK confirmed via `docker ps`

```
docker ps
CONTAINER ID   IMAGE                STATUS                   PORTS
2d5b75debb82   dailytask-backend    Up 3 minutes (healthy)   0.0.0.0:8000->8000/tcp
5c707d1002ae   dailytask-frontend   Up 3 minutes             0.0.0.0:8501->8501/tcp
```

`dailytask-backend-1` shows **`(healthy)`** — confirming the `HEALTHCHECK` instruction (a Python `urllib` call to `/health` every 30s, with a 60s start grace period) is running and passing correctly. The frontend has no `HEALTHCHECK` defined (not required by the mission — only the backend needed one), so it correctly shows no health status annotation.

## End-to-end verification through the actual UI

Opened `http://localhost:8501` in a browser (the frontend container), asked "What's my copay on the Gold PPO plan?", and received the correct answer: **"The copay for the Gold PPO plan is 10%."**

This is the real proof the whole stack works together: the **frontend container** correctly reached the **backend container** via `http://backend:8000` (Docker's internal service-name DNS), and the **backend container** correctly reached **Ollama running on the host Mac** via `http://host.docker.internal:11434/v1` — both of the gotchas identified above were genuinely fixed, not just theoretically addressed.

## Summary

All Day 28 requirements confirmed with real evidence, not just "it should work": multi-stage builds for both services, `docker-compose.yml` wiring both services with a volume-mounted Chroma/SQLite data layer and secrets via `env_file` only, `/health` responding both externally and internally, `HEALTHCHECK` correctly reporting `(healthy)` in `docker ps`, and a full round-trip question answered correctly through the actual browser UI running entirely in containers.
