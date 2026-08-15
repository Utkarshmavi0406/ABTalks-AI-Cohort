# Observability Notes — Day 30

## Step 1-2: Langfuse tracing wired in

`coverage-chatbot-api/main.py`'s `/chat` endpoint now wraps the actual LLM generation call in a Langfuse observation span:

```python
with langfuse_client.start_as_current_observation(
    name="generate_answer", as_type="generation", model=MODEL, input=augmented_context,
) as generation:
    ...
    generation.update(output=full_answer, usage_details={"input": input_tokens, "output": output_tokens})
```

**API note:** the `langfuse` package (4.x) is a full rewrite from the older `@observe` decorator + `trace()` API most tutorials describe — it's now built on OpenTelemetry, using `start_as_current_observation()` as a context manager and `.update()` to attach the final output/usage once the stream completes. Verified this pattern works correctly with a generator function (the streaming `/chat` handler) before wiring it into the real endpoint.

## Step 3: traces confirmed live in the Langfuse dashboard

Confirmed via the actual dashboard, not just "should work":

- **Traces tab** showed **3 total traces tracked**, all named `generate_answer`.
- Opening an individual trace showed:
  - **Latency:** 18.52s (captured automatically by the span)
  - **Model:** `qwen3:8b`
  - **Tokens:** 100 prompt → 15 completion (Σ 115)
  - **Full input:** the complete augmented context (conversation history, remembered plan, retrieved SQL/vector context, and the question)
  - **Full output:** the actual generated answer text

All four required data points (latency, tokens, full prompt, full response) are genuinely present and correct.

## Step 4: kubectl debugging on a deliberately broken pod

**Break applied:** added a bad `OLLAMA_BASE_URL` env var directly to `backend-deployment.yaml` (`http://this-host-does-not-exist:11434/v1`), overriding the working value from the Secret, and reapplied.

**Key finding — the pod passed its health checks anyway.** `kubectl get pods` showed the new pod as `1/1 Running` immediately. This is because `/health` is a static endpoint that doesn't actually exercise the Ollama connection — so Kubernetes had no way to know anything was wrong. Only sending a real `/chat` request revealed the failure:
```
data: [ERROR] The connection was lost while generating a response. Please try again.
```

**`kubectl logs <pod>`** showed the real story clearly: `/health` returning `200 OK` continuously (probes passing every time), while the actual request failed:
```
[LOG] session=... user_message='What is my copay on the Gold PPO plan?'
[ERROR] /chat stream dropped for session ... after 1.80s: Connection error.
```

**`kubectl describe pod <pod>`** showed the actual root cause directly, under `Environment:`:
```
Environment:
  OLLAMA_BASE_URL:  http://this-host-does-not-exist:11434/v1
```
The `Events` section, by contrast, showed nothing unusual (`Scheduled`, `Pulled`, `Created`, `Started` — all normal), since from Kubernetes' perspective the container started fine.

**Takeaway:** `describe pod` and `logs -f` do genuinely different diagnostic jobs. `describe pod` is the fast path to spot a misconfigured environment variable or resource directly. `logs -f` is where you'd actually see the resulting runtime failure that config caused. Neither alone would have told the whole story, and the current `/health` check has a real, documented blind spot: it can't detect a broken upstream dependency (Ollama, in this case), only that the FastAPI process itself is alive.

**Fix reverted** and confirmed working again with a real `/chat` request through `kubectl port-forward`.

## Step 5: sketched production alerts

Three alerts that would matter in a real deployment of this system, based directly on what today's debugging actually surfaced:

1. **Error-rate threshold:** alert if `/chat` requests logging `[ERROR] /chat stream dropped` (already logged today's incident in exactly this format) exceed **5% of requests over a 5-minute window**. This is the alert that would have caught today's broken-pod scenario immediately, instead of only being discoverable by manually testing a real request — a real gap our current `/health` check has.
2. **p95 latency threshold:** alert if p95 latency across `/chat` requests exceeds **15 seconds** (informed by real observed latency — today's trace showed 18.52s for a single request under otherwise-normal conditions, meaning our actual baseline latency is already close to what would traditionally be considered a "slow" threshold; a production system would need real baseline data before picking this number with confidence, but 15s is a reasonable starting point given what we've observed).
3. **Daily cost ceiling:** alert if the summed `estimated_cost` from Day 26's `usage_log` table exceeds a **daily budget threshold** (e.g. $10/day, illustrative given this project uses free local Ollama rather than a real paid API) — protecting against a runaway loop, an unexpected traffic spike, or a bug causing repeated unnecessary LLM calls.

A real production version of this system would also need a **health check that actually exercises Ollama connectivity** (e.g. a lightweight ping to `/v1/models`, not just returning a static `{"status": "ok"}`), directly motivated by today's finding that the current probe cannot detect this exact class of failure.

## The debugging journey (worth documenting honestly)

Today's actual path to a working `generate_answer` trace involved significantly more troubleshooting than the tracing code itself, and the root causes are worth recording for future reference:

1. **iCloud file eviction.** The project folder lived inside `~/Desktop`, which syncs to iCloud. macOS's "Optimize Mac Storage" had started evicting large, rarely-touched files (like `.venv`, later `chroma_data`) to iCloud-only, causing them to hang or outright fail (`NSFileProviderErrorDomain error -5009`) when Python tried to read them. Root cause: `.venv` had grown to ~3.5GB+ across 30 days, and Docker/Minikube's storage usage from Days 28-29 likely pushed local disk pressure high enough to trigger eviction on a folder that was never a target before.
2. **A stale, unrelated venv activation** after a terminal session restart briefly caused a `ModuleNotFoundError` unrelated to the real issue.
3. **A rebuilt venv hit a genuine, unrelated packaging failure**: `guardrails-ai`'s dependency resolver initially pulled a very old `lxml<5.0`, which has no prebuilt wheel for Python 3.14 and fails to compile from source (removed/changed CPython internals). Fixed by pinning `guardrails-ai==0.10.2` directly with `--only-binary=:all:`.
4. **Port 8000 conflicts**, twice — once from stale local `uvicorn` processes, once from the Day 28 `docker-compose` stack still running in the background the whole time without being noticed.
5. **Two real `.env` bugs**: `OLLAMA_BASE_URL` was left pointing at `host.docker.internal` (Docker-only, doesn't resolve when running locally without Docker Desktop active) instead of `localhost`; separately, the Langfuse host variable was misnamed `LANGFUSE_BASE_URL` instead of the SDK's actual expected `LANGFUSE_HOST`, and had unnecessary quote marks around the values.
6. **Minikube's kubectl context went stale** after Docker Desktop restarted mid-session (port mapping changed), requiring `minikube update-context` before `kubectl` commands worked again.

None of these were caused by the Langfuse integration itself — every one was environment/infrastructure friction uncovered along the way. Worth keeping this record since several of these (the `.env` variable name mismatch especially) are the kind of mistake that's easy to reintroduce later without realizing it.
