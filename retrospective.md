# Retrospective — 30-Day AI Cohort

## What worked well

**The layered architecture held up remarkably well over 30 days.** Starting with a clean split — SQL for structured data, vector search for policy text, a router to combine them (Day 10) — meant that every later addition (memory on Day 20, guardrails on Day 25, caching on Day 26) could be inserted as a well-defined layer around that core, rather than requiring a rewrite. By Day 31, the `/chat` endpoint has rate limiting, input guardrails, caching, retrieval, generation, output guardrails, usage logging, and tracing all composed together — and it's still comprehensible because each layer was added deliberately, one day at a time, on top of a stable foundation.

**Testing against real evidence, not assumptions, consistently paid off.** The RAGAS-style evaluation (Day 27) caught a genuine retrieval bug — comparison questions like "which plan has the lowest premium" were silently returning empty context — that would never have surfaced from casual manual testing. The A/B experiment (Day 26) and adversarial tests (Day 25) both produced results that meaningfully changed what shipped, rather than just confirming what was already assumed.

**Local-first development (Ollama, no paid API) removed cost anxiety entirely**, which made it easy to test aggressively — dozens of LLM calls per debugging session, without ever worrying about a bill.

## What was harder than expected

**Environment and infrastructure friction consumed far more time than the actual application logic**, especially in the back half of the program. Days 28-31 alone involved: a Docker networking gotcha (`host.docker.internal`), a corrupted SQLite file from concurrent access, an entire day chasing what turned out to be a silent iCloud file-eviction problem after `.venv` grew large enough for macOS to start treating it as a low-priority file, a stale `kubectl` context, and — on the very last day — Minikube's own container storage becoming corrupted mid-operation. None of these were mistakes in the *application* code; all of them were the accumulated cost of running a genuinely full local stack (Docker, Kubernetes, a multi-GB Python environment, a local LLM) on a single laptop for 30 days straight.

**Library API churn was a recurring, unglamorous tax.** Across the program: `pinecone-client` renamed, `create_react_agent` removed from LangChain, the MCP SDK's `FastMCP` class renamed to `MCPServer`, Claude Desktop's entire MCP registration mechanism changed from JSON config to packaged extensions, `ragas` broke on import due to an unrelated `langchain-community` deprecation, and `langfuse` turned out to be a full OpenTelemetry-based rewrite from the API most tutorials still describe. None of this was foreseeable in advance — it required verifying the actual installed API against real documentation or direct testing every single time, rather than trusting memorized knowledge of any of these libraries.

**Silent failures were consistently more dangerous than loud ones.** The empty-vector-database bug in Kubernetes (Day 29), the "no such table" from a corrupted SQLite file, and today's stale-Docker-image issue all shared the same shape: nothing crashed, nothing logged an error, the system just quietly did the wrong thing (or nothing at all) and looked fine from the outside. Every one of these needed active, skeptical verification — running a real test and checking a real result — rather than trusting a green checkmark.

## What I'd do differently starting over

1. **Move the project out of any cloud-synced folder (like Desktop) on day one**, not day 30. This single decision cost most of a full day near the end of the program and was entirely avoidable — a multi-GB Python/Docker project simply doesn't belong somewhere that silently evicts files to save space.
2. **Set up a minimal CI step earlier** — even something as simple as a script that rebuilds the Docker image and runs a smoke test whenever `requirements.txt` or the app code changes. Today's Langfuse-trace mystery took an hour to trace back to "the image was never rebuilt" — a problem a five-line automated check would have caught in seconds.
3. **Write the "what does success actually look like" test for a feature *before* building it**, more consistently. The days where this happened naturally (Day 26's A/B experiment, Day 27's RAGAS evaluation) produced the clearest, most actionable results of the whole program; the days where testing was more ad-hoc took longer to build real confidence in.
