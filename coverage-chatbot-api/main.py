"""
coverage-chatbot-api/main.py
Day 30 — Monitoring & Observability

Adds Langfuse tracing around the LLM generation call: every request logs
latency (automatic, via the span), token usage, and the full prompt/
response. Everything from Day 20-29 (memory, guardrails, caching, rate
limiting, usage logging) is unchanged.
"""

import re
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "coverage.db"
sys.path.insert(0, str(ROOT))

from retrieval_engine import retrieve  # noqa: E402
from rag_chatbot import generate_answer_stream, client, MODEL  # noqa: E402
from redact_pii import redact_pii  # noqa: E402  (Day 25)
from guardrails_config import check_input_guardrail, check_output_guardrail  # noqa: E402  (Day 25)
from langfuse import get_client as get_langfuse_client  # noqa: E402  (Day 30)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Day 30: Langfuse client, reads LANGFUSE_PUBLIC_KEY /
# LANGFUSE_SECRET_KEY / LANGFUSE_HOST from the environment automatically ----------
langfuse_client = get_langfuse_client()

LAST_N_TURNS = 10
TOKEN_BUDGET = 2000

# ---------- Day 26: token counting, now in its own module ----------
from token_utils import count_tokens  # noqa: E402

# Illustrative reference rate for cost-tracking purposes. Our actual model
# (qwen3:8b via local Ollama) is free -- this rate is a stand-in so the
# cost-logging mechanism can be demonstrated as if against a paid API.
INPUT_COST_PER_1K = 0.00015   # illustrative $/1K input tokens
OUTPUT_COST_PER_1K = 0.0006   # illustrative $/1K output tokens

# ---------- Day 26: rate limiting (manual dict-based counter) ----------
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60
_request_log: dict[str, list[float]] = {}  # member_id -> [timestamps]

# ---------- Day 26: exact-match cache for general (non-member-specific) questions ----------
_response_cache: dict[str, dict] = {}  # normalized_question -> {"answer", "citations"}


# ---------- Step 1: conversations table ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    # ---------- Day 26 Step 2: usage log table ----------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            estimated_cost REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


init_db()


def log_usage(session_id: str, input_tokens: int, output_tokens: int):
    estimated_cost = (input_tokens / 1000) * INPUT_COST_PER_1K + (output_tokens / 1000) * OUTPUT_COST_PER_1K
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO usage_log (session_id, timestamp, input_tokens, output_tokens, estimated_cost) VALUES (?, ?, ?, ?, ?)",
        (session_id, datetime.now(timezone.utc).isoformat(), input_tokens, output_tokens, estimated_cost),
    )
    conn.commit()
    conn.close()
    print(f"[USAGE] session={session_id} input_tokens={input_tokens} output_tokens={output_tokens} "
          f"estimated_cost=${estimated_cost:.6f}")


# ---------- Step 3: rate limiter ----------
def check_rate_limit(member_id: str) -> bool:
    """Returns True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    timestamps = _request_log.setdefault(member_id, [])
    # drop timestamps outside the window
    timestamps[:] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW_SECONDS]

    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    timestamps.append(now)
    return True


# ---------- Step 4: exact-match cache ----------
def normalize_question(text: str) -> str:
    return " ".join(text.strip().lower().split())


def is_member_specific(question: str) -> bool:
    """Member-specific questions (e.g. claim lookups) must never be cached,
    since the same question text could legitimately mean different things
    for different members' claim histories."""
    return bool(re.search(r"c-?\d{3,5}", question, re.IGNORECASE))


def get_cached_response(question: str) -> Optional[dict]:
    if is_member_specific(question):
        return None
    key = normalize_question(question)
    return _response_cache.get(key)


def store_cached_response(question: str, answer: str, citation_ids: list[str]):
    if is_member_specific(question):
        return
    key = normalize_question(question)
    _response_cache[key] = {"answer": answer, "citations": citation_ids}


# ---------- Step 2: save turns ----------
def save_turn(session_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def load_history(session_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "role": r[1], "content": r[2], "timestamp": r[3]} for r in rows]


def replace_turns_with_summary(session_id: str, turn_ids: list[int], summary_text: str, earliest_timestamp: str):
    """Delete the given turn rows and insert one 'summary' row in their place.

    The summary is backdated to the earliest replaced turn's timestamp so it
    still sorts correctly (oldest-first) relative to any turns added later --
    otherwise a second round of summarization would scramble conversation
    order, since a freshly-inserted row would always get the newest timestamp
    regardless of how old the content it represents actually is.
    """
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" for _ in turn_ids)
    conn.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", turn_ids)
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, "summary", summary_text, earliest_timestamp),
    )
    conn.commit()
    conn.close()


# ---------- Step 4: summarize the oldest half once over the token budget ----------
def summarize_turns(turns: list[dict]) -> str:
    transcript = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
    prompt = (
        "Summarize the following conversation between a member and a health coverage "
        "assistant in 2-4 sentences. Preserve any specific facts mentioned (plan names, "
        "claim IDs, dollar amounts) since they may be needed later.\n\n"
        f"{transcript}"
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def maybe_summarize(session_id: str, history: list[dict]) -> tuple[list[dict], int, int]:
    """Returns (possibly-trimmed history, tokens_before, tokens_after)."""
    full_text = "\n".join(t["content"] for t in history)
    tokens_before = count_tokens(full_text)

    if tokens_before <= TOKEN_BUDGET or len(history) < 4:
        return history, tokens_before, tokens_before

    half = len(history) // 2
    oldest_half = history[:half]
    newest_half = history[half:]

    summary_text = summarize_turns(oldest_half)
    replace_turns_with_summary(
        session_id,
        [t["id"] for t in oldest_half],
        summary_text,
        earliest_timestamp=oldest_half[0]["timestamp"],
    )

    new_history = [{"id": -1, "role": "summary", "content": summary_text, "timestamp": ""}] + newest_half
    new_text = "\n".join(t["content"] for t in new_history)
    tokens_after = count_tokens(new_text)

    print(f"[SUMMARIZE] session={session_id} {len(oldest_half)} turns summarized; "
          f"tokens {tokens_before} -> {tokens_after}")

    return new_history, tokens_before, tokens_after


# ---------- Step 3: extract plan_id/plan name already mentioned ----------
def extract_mentioned_plan(history: list[dict]) -> Optional[str]:
    plan_display_names = {
        "gold ppo": "Gold PPO",
        "silver hmo": "Silver HMO",
        "bronze hmo": "Bronze HMO",
    }
    for turn in reversed(history):  # most recent mention wins
        if turn["role"] != "user":
            continue
        match = re.search(r"(gold ppo|silver hmo|bronze hmo)", turn["content"], re.IGNORECASE)
        if match:
            return plan_display_names[match.group(1).lower()]
    return None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    member_id: str
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "version": "v2"}


@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    # ---------- Step 3: rate limiting, checked first (cheapest check) ----------
    if not check_rate_limit(request.member_id):
        print(f"[RATE LIMIT] member={request.member_id} exceeded {RATE_LIMIT_MAX_REQUESTS} requests/{RATE_LIMIT_WINDOW_SECONDS}s")

        def rate_limited_generator():
            canned = "You're sending requests too quickly. Please wait a moment and try again."
            yield f"data: {canned}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(rate_limited_generator(), media_type="text/event-stream")

    # ---------- Step 4: input guardrail, checked BEFORE any LLM call ----------
    is_safe, block_reason = check_input_guardrail(request.message)
    print(f"[LOG] session={session_id} user_message={redact_pii(request.message)!r}")

    if not is_safe:
        print(f"[GUARDRAIL] session={session_id} INPUT BLOCKED: {block_reason}")

        def blocked_generator():
            canned = "I can't process that request. Please rephrase your question about your own coverage or claims."
            save_turn(session_id, "user", request.message)
            save_turn(session_id, "assistant", canned)
            yield f"data: {canned}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(blocked_generator(), media_type="text/event-stream")

    # ---------- Step 4 (Day 26): exact-match cache check ----------
    cached = get_cached_response(request.message)
    if cached is not None:
        print(f"[CACHE HIT] session={session_id} question={request.message!r}")

        def cached_generator():
            save_turn(session_id, "user", request.message)
            save_turn(session_id, "assistant", cached["answer"])
            yield f"data: {cached['answer']}\n\n"
            if cached["citations"]:
                yield f"data: [CITATIONS] {'|'.join(cached['citations'])}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(cached_generator(), media_type="text/event-stream")

    save_turn(session_id, "user", request.message)

    def event_generator():
        start_time = time.monotonic()
        full_answer = ""
        classification = "error"
        citation_ids: list[str] = []

        # Step 3: load history, apply summarization if needed, extract plan
        history = load_history(session_id)
        history, tokens_before, tokens_after = maybe_summarize(session_id, history)
        recent_turns = history[-LAST_N_TURNS:]
        mentioned_plan = extract_mentioned_plan(history)

        # If the member already told us their plan earlier in the conversation
        # but doesn't restate it in this specific question, splice it in before
        # retrieval -- otherwise sql_lookup() has no plan name to filter on and
        # silently returns nothing, even though we "know" the answer from memory
        plan_already_in_question = mentioned_plan and re.search(
            r"(gold ppo|silver hmo|bronze hmo)", request.message, re.IGNORECASE
        )
        retrieval_query = request.message
        if mentioned_plan and not plan_already_in_question:
            retrieval_query = f"{request.message} (for the {mentioned_plan} plan)"

        try:
            retrieval_result = retrieve(retrieval_query)
        except Exception as e:
            print(f"[ERROR] /chat retrieve failed for session {session_id}: {e}")
            yield "data: [ERROR] Something went wrong looking up your coverage information. Please try again.\n\n"
            yield "data: [DONE]\n\n"
            return

        classification = retrieval_result["classification"]
        retrieved_context = retrieval_result["context"]
        citation_ids = [c["id"] for c in retrieval_result.get("vector_results", [])]

        # Build the augmented context: conversation history + remembered plan
        # + freshly retrieved policy/coverage info for this specific question
        history_block = "\n".join(f"{t['role']}: {t['content']}" for t in recent_turns)
        plan_note = f"\n[Member's plan, mentioned earlier in this conversation]: {mentioned_plan}\n" if mentioned_plan else ""
        augmented_context = (
            f"[Conversation so far -- for your reference only, do not repeat or quote it back]\n{history_block}\n"
            f"{plan_note}\n"
            f"[Retrieved policy/coverage information]\n{retrieved_context}\n\n"
            f"Answer only the member's current question below. Do not restate the question."
        )

        request_tokens = count_tokens(augmented_context)
        print(f"[TOKENS] session={session_id} history_tokens_before_summarize={tokens_before} "
              f"history_tokens_after_summarize={tokens_after} full_request_context_tokens={request_tokens}")

        # ---------- Day 30: wrap the LLM call in a Langfuse generation span.
        # Latency is captured automatically (span start/end time); we attach
        # the full prompt now and the full response + token usage once the
        # stream finishes, inside the finally block below. ----------
        with langfuse_client.start_as_current_observation(
            name="generate_answer",
            as_type="generation",
            model=MODEL,
            input=augmented_context,
        ) as generation:
            try:
                for token in generate_answer_stream(request.message, augmented_context):
                    full_answer += token
                    safe_token = token.replace("\n", "\\n")
                    yield f"data: {safe_token}\n\n"
            except Exception as e:
                elapsed = time.monotonic() - start_time
                print(f"[ERROR] /chat stream dropped for session {session_id} after {elapsed:.2f}s: {e}")
                yield "data: [ERROR] The connection was lost while generating a response. Please try again.\n\n"
            finally:
                elapsed = time.monotonic() - start_time
                print(f"[TIMING] /chat session={session_id} classification={classification} took {elapsed:.2f}s")

                # ---------- Step 5: output guardrail ----------
                # Limitation, stated plainly: since the answer was already
                # streamed token-by-token, a flagged output can't be un-sent.
                # This checks the FULL assembled answer after the fact, logs any
                # PHI/medical-advice issue, saves the SAFE (redacted or
                # disclaimer-replaced) version to persistent history rather than
                # the raw text, and sends an additional safety-notice event so
                # the client can display a correction. A production system would
                # need to check the answer before streaming begins (e.g. a
                # non-streamed pre-check call) to actually prevent a flagged
                # response from ever reaching the member.
                if full_answer:
                    is_output_safe, safe_answer = check_output_guardrail(full_answer)
                    print(f"[LOG] session={session_id} assistant_answer={redact_pii(full_answer)!r}")

                    # ---------- Day 26 Step 1 + 2: token counting and usage logging
                    # on every prompt + completion ----------
                    input_tokens = request_tokens
                    output_tokens = count_tokens(full_answer)
                    log_usage(session_id, input_tokens, output_tokens)

                    # ---------- Day 30: attach full latency/tokens/prompt/response
                    # to the Langfuse trace ----------
                    generation.update(
                        output=full_answer,
                        usage_details={"input": input_tokens, "output": output_tokens},
                    )

                    if not is_output_safe:
                        print(f"[GUARDRAIL] session={session_id} OUTPUT FLAGGED — saving redacted/disclaimer version to history")
                        save_turn(session_id, "assistant", safe_answer)
                        yield f"data: [SAFETY NOTICE] {safe_answer}\n\n"
                    else:
                        save_turn(session_id, "assistant", full_answer)
                        # ---------- Day 26 Step 4: store in cache only for safe,
                        # non-member-specific answers ----------
                        store_cached_response(request.message, full_answer, citation_ids)

        if citation_ids:
            yield f"data: [CITATIONS] {'|'.join(citation_ids)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/history/{session_id}")
def get_history(session_id: str):
    history = load_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"No session found with id {session_id}")
    return {"session_id": session_id, "turns": history}
