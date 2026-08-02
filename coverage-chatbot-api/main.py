"""
coverage-chatbot-api/main.py
Day 16 — Chatbot Backend & API Integration

Orchestrates: receive question -> retrieve() (Day 10) -> generate_answer()
(Day 11) -> return response, with session tracking and conversation history.
"""

import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# rag_chatbot.py, retrieval_engine.py, coverage.db, knowledge_base.jsonl, etc.
# all live at the Daily Task root, one level up from this file.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag_chatbot import retrieve_and_answer  # noqa: E402  (Day 11: chains Day 10's retrieve() + generate_answer())

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Step 3: session store ----------
# In-memory, keyed by session_id. Each entry is a list of turn dicts.
# Resets on server restart -- fine for this exercise; a SQLite-backed
# version would swap this dict for a `sessions` table.
SESSION_STORE: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    member_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    member_id: str
    answer: str
    classification: str
    response_time_seconds: float


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Step 1 + 2: POST /chat ----------
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = []

    # Log the incoming user turn
    SESSION_STORE[session_id].append({
        "role": "user",
        "content": request.message,
        "member_id": request.member_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # ---------- Step 6: timing + error handling ----------
    start_time = time.monotonic()
    try:
        result = retrieve_and_answer(request.message)
    except Exception as e:
        elapsed = time.monotonic() - start_time
        print(f"[ERROR] /chat failed for session {session_id} after {elapsed:.2f}s: {e}")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong generating a response. Please try again or contact support.",
        )
    elapsed = time.monotonic() - start_time
    print(f"[TIMING] /chat session={session_id} classification={result['classification']} took {elapsed:.2f}s")

    # Log the assistant turn
    SESSION_STORE[session_id].append({
        "role": "assistant",
        "content": result["answer"],
        "classification": result["classification"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return ChatResponse(
        session_id=session_id,
        member_id=request.member_id,
        answer=result["answer"],
        classification=result["classification"],
        response_time_seconds=round(elapsed, 3),
    )


# ---------- Step 4: GET /history/{session_id} ----------
@app.get("/history/{session_id}")
def get_history(session_id: str):
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"No session found with id {session_id}")
    return {"session_id": session_id, "turns": SESSION_STORE[session_id]}
