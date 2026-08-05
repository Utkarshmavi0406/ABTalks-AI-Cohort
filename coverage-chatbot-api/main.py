"""
coverage-chatbot-api/main.py
Day 20 — Conversation Memory & Context Management

Persists every chat turn to a SQLite `conversations` table, injects the
last N turns plus any plan the member has already mentioned into the
prompt, and summarizes the oldest half of a long conversation once it
exceeds ~2000 tokens to keep the context window bounded.
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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LAST_N_TURNS = 10
TOKEN_BUDGET = 2000

# ---------- token counting (tiktoken, with a rough-estimate fallback) ----------
try:
    import tiktoken
    _ENCODING = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENCODING.encode(text))
except Exception as e:
    print(f"[WARNING] tiktoken unavailable ({e}); falling back to a rough word-based estimate")

    def count_tokens(text: str) -> int:
        # ~4 characters per token is a commonly used rough estimate
        return max(1, len(text) // 4)


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
    conn.commit()
    conn.close()


init_db()


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
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

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
            if full_answer:
                save_turn(session_id, "assistant", full_answer)
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
