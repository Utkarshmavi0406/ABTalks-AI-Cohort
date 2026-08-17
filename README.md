# AI Coverage Assistant

A production-shaped health-coverage chatbot, built end-to-end over a 30-day AI cohort program: retrieval-augmented generation over structured (SQL) and unstructured (vector) data, conversation memory, safety guardrails, agentic tool use via MCP, containerization, Kubernetes deployment, and observability — all running on a local LLM (Ollama) with zero API cost.

**⚠️ This is a coursework/learning project using entirely synthetic data.** No real member data was ever used. See [`GOVERNANCE.md`](GOVERNANCE.md) for the full data-sensitivity and compliance notes — **a formal legal/compliance review would be required before this touches any real member data.**

## What it does

Ask it about a (fake) health plan's deductibles, copays, coverage exclusions, or claim statuses, in natural conversation:

> "What's my copay on the Gold PPO plan?" → *"The copay for the Gold PPO plan is 10%."*
> "Is cosmetic surgery covered?" → *(correctly declines, cites the actual exclusion, shows a data card)*
> "What about the deductible?" *(no plan restated)* → *(correctly remembers you're asking about Gold PPO)*

## Architecture

```
Streamlit frontend  ──HTTP──▶  FastAPI backend  ──┬──▶ SQLite (plans, claims, conversations, usage)
                                                   ├──▶ ChromaDB (policy text embeddings)
                                                   ├──▶ Ollama (qwen3:8b, local LLM)
                                                   └──▶ Langfuse (tracing)
```

A query router (`retrieval_engine.py`) classifies each question and pulls from SQL, vector search, or both, merging results into one grounded context block before generation. Every request also passes through rate limiting, input/output safety guardrails, and an exact-match cache for repeated general questions.

## What was built, by phase

| Phase | Highlights |
|---|---|
| **Foundations** (Days 1-9) | Python/dev environment, local LLM via Ollama, structured (SQLite) + unstructured (PDF/DOCX/OCR) data ingestion, chunking, embeddings, vector DB comparison |
| **Retrieval & Chatbot Build** (Days 10-20) | Hybrid SQL/vector retrieval router, full RAG pipeline, prompt engineering (A/B tested), function calling, LoRA fine-tuning experiment, FastAPI + React/Streamlit full-stack app, SSE streaming, rich response cards, conversation memory with automatic summarization |
| **Agentic AI & MCP** (Days 21-24) | LangChain/LangGraph ReAct agent, multi-agent Router + Specialist architecture, a real MCP server exposing tools to Claude Desktop, full integration with resilience (timeouts, retries, graceful fallbacks) |
| **Governance & Evaluation** (Days 25-27) | PHI/PII redaction, input/output safety guardrails, adversarial red-teaming, token/cost tracking, rate limiting, response caching, A/B experiment on prompt variants, RAGAS-style automated evaluation (faithfulness, relevancy, context precision/recall) that caught and fixed a real retrieval bug |
| **Containerization, Kubernetes & Production** (Days 28-31) | Multi-stage Docker builds, `docker-compose` orchestration, Kubernetes deployment (Minikube) with Services, Secrets, health probes, scaling, zero-downtime rolling updates, Langfuse LLM observability, live `kubectl` incident debugging |

## Tech stack

**Backend:** FastAPI, SQLite, ChromaDB, sentence-transformers, OpenAI SDK (pointed at local Ollama)
**LLM:** `qwen3:8b` via Ollama — fully local, no API cost
**Safety:** `guardrails-ai`, custom PII redaction
**Agentic:** LangChain, LangGraph, MCP (Model Context Protocol)
**Frontend:** Streamlit
**Observability:** Langfuse (tracing), custom token/cost logging
**Infra:** Docker, Kubernetes (Minikube), `kubectl`

## Repo layout

```
Daily Task/
├── app.py                       ← Streamlit frontend
├── coverage-chatbot-api/
│   └── main.py                  ← FastAPI backend (the actual production chatbot)
├── retrieval_engine.py          ← SQL/vector routing (Day 10)
├── rag_chatbot.py                ← RAG generation (Day 11)
├── redact_pii.py                 ← PHI/PII redaction (Day 25)
├── guardrails_config.py          ← input/output safety guardrails (Day 25)
├── token_utils.py                ← token counting (Day 26)
├── mcp_server.py                  ← MCP server exposing coverage tools (Day 23)
├── multi_agent.py                 ← Router + Specialist multi-agent workflow (Day 22/24)
├── Dockerfile / Dockerfile.frontend / docker-compose.yml
├── k8s/                           ← Kubernetes manifests (Day 29)
├── GOVERNANCE.md                  ← data sensitivity, PHI/PII, compliance notes (Day 25)
├── ragas_scorecard.md             ← automated eval results + one real fix (Day 27)
├── ab_test_results.md             ← prompt A/B experiment results (Day 26)
├── adversarial_tests.md           ← red-team test results (Day 25)
├── capstone_walkthrough.md        ← final end-to-end test evidence (Day 31)
├── retrospective.md               ← what worked, what didn't (Day 31)
└── v2_roadmap.md                  ← prioritized next steps (Day 31)
```

## Running it locally

```bash
# 1. Start Ollama and pull the model
ollama pull qwen3:8b

# 2. Set up the environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r coverage-chatbot-api/requirements.txt
pip install -r requirements-frontend.txt

# 3. Configure environment variables
cp .env.example .env  # then fill in OLLAMA_BASE_URL, Langfuse keys if desired

# 4. Run the backend
cd coverage-chatbot-api && uvicorn main:app --reload

# 5. Run the frontend (separate terminal)
streamlit run app.py
```

**Or with Docker:**
```bash
docker compose up --build
```

**Or on Kubernetes (Minikube):**
```bash
minikube start
minikube image load dailytask-backend:latest
minikube image load dailytask-frontend:latest
kubectl create secret generic llm-secret --from-literal=OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
kubectl apply -f k8s/
minikube service frontend
```

## Key findings worth knowing

A few genuine bugs and gaps were found and either fixed or honestly documented along the way, rather than glossed over:

- **A real retrieval bug** where cross-plan comparison questions ("which plan has the lowest premium?") silently returned empty context — found via automated evaluation (Day 27), root-caused, and fixed.
- **A retrieval-layer PHI exposure risk**: adversarial testing found that a PHI-fishing question could pull a real enrollment record into the model's context, with only the model's own restraint preventing disclosure — documented as an unresolved gap in `GOVERNANCE.md`.
- **Multiple real infrastructure lessons** from Days 28-31 (Docker networking, a corrupted SQLite file, iCloud file-eviction breaking a multi-GB `.venv`, a stale Kubernetes image causing a working feature to silently produce no output) — all documented in `retrospective.md`.

See [`retrospective.md`](retrospective.md) and [`v2_roadmap.md`](v2_roadmap.md) for the full honest account of what worked, what was harder than expected, and what's prioritized next.

## Compliance

**This project is coursework using synthetic data only.** See [`GOVERNANCE.md`](GOVERNANCE.md) for the full governance checklist. Production use with real member data would require a formal HIPAA risk assessment, legal review, and professional security testing — none of which has been performed here.
