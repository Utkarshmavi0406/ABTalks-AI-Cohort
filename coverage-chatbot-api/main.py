"""
coverage-chatbot-api/main.py
Day 19 — adds citation chunk-ID tracking to the streaming /chat endpoint
(everything else unchanged from Day 18).
"""

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
sys.path.insert(0, str(ROOT))

from retrieval_engine import retrieve  # noqa: E402
from rag_chatbot import generate_answer_stream  # noqa: E402

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_STORE: dict[str, list[dict]] = {}


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

    if session_id not in SESSION_STORE:
        SESSION_STORE[session_id] = []

    SESSION_STORE[session_id].append({
        "role": "user",
        "content": request.message,
        "member_id": request.member_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    def event_generator():
        start_time = time.monotonic()
        full_answer = ""
        classification = "error"
        citation_ids: list[str] = []

        try:
            retrieval_result = retrieve(request.message)
        except Exception as e:
            print(f"[ERROR] /chat retrieve failed for session {session_id}: {e}")
            yield "data: [ERROR] Something went wrong looking up your coverage information. Please try again.\n\n"
            yield "data: [DONE]\n\n"
            return

        classification = retrieval_result["classification"]
        context = retrieval_result["context"]

        # Step 1: track which chunks were actually passed into context --
        # these are the vector-search results (policy text chunks), not the
        # SQL rows, since "citations" here means "which policy source did
        # this answer draw from"
        citation_ids = [c["id"] for c in retrieval_result.get("vector_results", [])]

        try:
            for token in generate_answer_stream(request.message, context):
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
                SESSION_STORE[session_id].append({
                    "role": "assistant",
                    "content": full_answer,
                    "classification": classification,
                    "citations": citation_ids,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            if citation_ids:
                yield f"data: [CITATIONS] {'|'.join(citation_ids)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/history/{session_id}")
def get_history(session_id: str):
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"No session found with id {session_id}")
    return {"session_id": session_id, "turns": SESSION_STORE[session_id]}
