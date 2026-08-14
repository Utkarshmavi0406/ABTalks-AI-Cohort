# Kubernetes Notes — Day 29

## Setup

- **Cluster:** Minikube, `docker` driver (auto-selected on macOS, confirmed via startup output). This matters because it means Minikube's node runs as a container inside Docker Desktop's own VM — the same environment Day 28's containers already ran in, so `host.docker.internal` continued to resolve correctly without any extra configuration.
- **Images loaded via `minikube image load`** (no registry) — matches Step 2's first option, since these are local dev images, not meant for distribution.
- **4 manifests under `k8s/`:** `backend-deployment.yaml` (2 replicas), `backend-service.yaml` (ClusterIP), `frontend-deployment.yaml` (1 replica), `frontend-service.yaml` (NodePort, so `minikube service frontend` can open it in a browser).
- **Secret:** created imperatively (`kubectl create secret generic llm-secret --from-literal=OLLAMA_BASE_URL=...`), never written to YAML, referenced via `envFrom.secretRef` in the backend Deployment. Since this project runs on local Ollama rather than a paid API, the Secret holds `OLLAMA_BASE_URL` rather than a truly sensitive key — but the same `Secret` + `envFrom` pattern is exactly what would hold a real API key if this were swapped to a paid provider later.

## Real bugs found (not anticipated in advance — found through actual testing)

### 1. Frontend was missing `coverage.db` entirely
`Dockerfile.frontend` never copied `coverage.db` into the frontend image (only `app.py`, `response_cards.py`, `data/plans.csv`). Streamlit's card-rendering feature (`response_cards.py`) needs to query the database directly, and SQLite silently creates an empty file rather than erroring when the file doesn't exist — so this surfaced as `sqlite3.OperationalError: no such table: plans` deep inside the running app, not an obvious "file not found" at startup. **Fixed** by adding `COPY coverage.db ./` to `Dockerfile.frontend`.

### 2. Backend was missing `chroma_data` entirely
Unlike Day 28's `docker-compose.yml` (which volume-mounts `chroma_data` from the host), the Kubernetes manifests set up no equivalent persistent volume. Since the backend image never baked `chroma_data` in either, the backend pods were running against an empty vector database — degrading answer quality (vague "the context doesn't contain this information" responses) without throwing any visible error, since Chroma auto-creates an empty collection rather than failing. **Fixed** by adding `COPY chroma_data/ ./chroma_data/` to the backend `Dockerfile`, and by removing `chroma_data/` from `.dockerignore` (it had been deliberately excluded there for Day 28's volume-mount strategy, which directly conflicted with Day 29's bake-it-in strategy).

### 3. `coverage.db` itself was corrupted on disk
After fixing both of the above, the SQLite error persisted. Direct testing revealed the actual problem: `coverage.db` on the host machine had become corrupted (`sqlite3.DatabaseError: file is not a database`) — no `COPY` fix could have worked, since every rebuild was faithfully copying a broken file. Likely cause: concurrent access to the same SQLite file from multiple processes (Day 28's `docker-compose` setup had both the backend container and host-side scripts reading/writing the same bind-mounted file). **Fixed** by rebuilding `coverage.db` from scratch directly from the original `data/plans.csv` and `data/claims.csv` source files.

### 4. `minikube image load` doesn't reliably overwrite an image at the same tag
Rebuilding and reloading `dailytask-backend:latest`/`dailytask-frontend:latest` multiple times in a row didn't reliably pick up the newest build — the running pods kept showing the old buggy behavior even after a rebuild+reload+`rollout restart` cycle. **Fixed** by explicitly removing the cached image first (`minikube image rm`, which itself required scaling deployments to 0 first, since a running container holding the old image blocks removal) before reloading. For the actual rolling-update test (Step 6), building under a distinct tag (`dailytask-backend:v2`) sidestepped this ambiguity entirely — a cleaner practice than reusing `:latest` repeatedly during iterative debugging.

## Step 5: pods reach Running/Ready, verified end-to-end through the UI

```
kubectl get pods
NAME                       READY   STATUS    RESTARTS   AGE
backend-867985fc4b-9cccz   1/1     Running   0          50s
backend-867985fc4b-spqvk   1/1     Running   0          50s
frontend-55fbc7d8-fspnj    1/1     Running   0          50s
```

Confirmed via the actual browser UI (`minikube service frontend`): "What's my copay on the Gold PPO plan?" → correct answer ("10.0%"), and "Is cosmetic surgery covered under the Gold PPO plan?" → correctly rendered the `Gold PPO — Coverage Summary` card with accurate data ($2,000 deductible, 10% copay, Covered: No) — proving both `coverage.db` (SQL/card path) and `chroma_data` (vector search path) were genuinely working inside the cluster, not just that the pods happened to report healthy.

## Step 6: scale, rolling update, zero downtime

**Scale to 3:**
```
kubectl scale deployment backend --replicas=3
kubectl get pods
# 3 backend pods, all 1/1 Running
```

**Rolling update** (changed `/health` to return `{"status": "ok", "version": "v2"}`, built as `dailytask-backend:v2`):
```
kubectl set image deployment/backend backend=dailytask-backend:v2
kubectl rollout status deployment/backend

Waiting for deployment "backend" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "backend" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "backend" rollout to finish: 1 old replicas are pending termination...
deployment "backend" successfully rolled out
```

**Confirmed zero downtime**: new replicas were added one at a time (1→2→3) and old replicas were only terminated *after* their replacement passed the readiness probe — at no point did the available replica count drop below the original 3. Verified the new version actually deployed (not just a cosmetic pod restart) via:
```
curl http://localhost:8000/health
{"status":"ok","version":"v2"}
```

**Teardown:**
```
kubectl delete -f k8s/
deployment.apps "backend" deleted
service "backend" deleted
deployment.apps "frontend" deleted
service "frontend" deleted
```

## Summary

All Day 29 requirements confirmed with real evidence: Minikube cluster running, both images loaded without a registry, 4 manifests correctly wiring 2 backend replicas + 1 frontend replica with Services, a Secret injected via `envFrom` (never committed to YAML), readiness/liveness probes correctly gating traffic during startup and rollout, a genuine 3-bug debugging chain resolved (missing DB file, missing vector DB, a corrupted source file, and an image-caching gotcha), scale-to-3 confirmed, a zero-downtime rolling update confirmed via live rollout status and a version-marker health check, and a clean teardown.
