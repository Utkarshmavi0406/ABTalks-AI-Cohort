# Backend Chat Test — Day 16

Tested `POST /chat` and `GET /history/{session_id}` against the live FastAPI server (`uvicorn main:app --reload`), sending 3 sequential messages under the same `session_id` and confirming `/history` reflects all of them.

## Setup

```
cd "Daily Task/coverage-chatbot-api"
uvicorn main:app --reload
```

Confirmed `/health` responds correctly before testing:
```
curl http://localhost:8000/health
{"status":"ok"}
```

## Test 1 — first message

**Request:**
```
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-1", "member_id": "M1001", "message": "What is my copay on the Gold PPO plan?"}'
```

**Response:**
```json
{"session_id":"test-session-1","member_id":"M1001","answer":"The copay for the Gold PPO plan is 10%.","classification":"structured","response_time_seconds":19.046}
```

## Test 2 — second message, same session_id

**Request:**
```
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-1", "member_id": "M1001", "message": "Is cosmetic surgery excluded from coverage?"}'
```

**Response:**
```json
{"session_id":"test-session-1","member_id":"M1001","answer":"Yes, cosmetic surgery is excluded from coverage as stated in the context.","classification":"unstructured","response_time_seconds":11.484}
```

## Test 3 — third message, same session_id

**Request:**
```
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-1", "member_id": "M1001", "message": "What is the status of claim C1001?"}'
```

**Response:**
```json
{"session_id":"test-session-1","member_id":"M1001","answer":"The status of claim C1001 is **Pending**.","classification":"structured","response_time_seconds":9.235}
```

## History check

**Request:**
```
curl http://localhost:8000/history/test-session-1
```

**Response:** (abridged for readability — full response confirmed 6 turns)
```json
{
  "session_id": "test-session-1",
  "turns": [
    {"role": "user", "content": "What is my copay on the Gold PPO plan?", "member_id": "M1001", "timestamp": "2026-08-02T03:54:36.227338+00:00"},
    {"role": "assistant", "content": "The copay for the Gold PPO plan is 10%.", "classification": "structured", "timestamp": "2026-08-02T03:54:55.273671+00:00"},
    {"role": "user", "content": "Is cosmetic surgery excluded from coverage?", "member_id": "M1001", "timestamp": "2026-08-02T03:55:36.426472+00:00"},
    {"role": "assistant", "content": "Yes, cosmetic surgery is excluded from coverage as stated in the context.", "classification": "unstructured", "timestamp": "2026-08-02T03:55:47.910650+00:00"},
    {"role": "user", "content": "What is the status of claim C1001?", "member_id": "M1001", "timestamp": "2026-08-02T03:56:11.125087+00:00"},
    {"role": "assistant", "content": "The status of claim C1001 is **Pending**.", "classification": "structured", "timestamp": "2026-08-02T03:56:20.360491+00:00"}
  ]
}
```

**Confirmed:** all 6 turns present (3 user + 3 assistant), correctly ordered, each with a distinct timestamp, all tied to the same `session_id`. `/history` accurately reflects the full conversation.

## Response times observed

| Message | Classification | Response time |
|---|---|---|
| 1 (copay lookup) | structured | 19.046s |
| 2 (exclusion check) | unstructured | 11.484s |
| 3 (claim status) | structured | 9.235s |

Times decrease across the run, likely due to model warm-up on the first call. All well within acceptable range for a local Ollama model on Apple Silicon.

## Error handling (Step 6)

The `/chat` endpoint wraps the `retrieve_and_answer()` call in a try/except block. On failure, it returns a 500 with a graceful message ("Something went wrong generating a response. Please try again or contact support.") instead of crashing, and logs the error with elapsed time to the server console. Every successful call also logs a `[TIMING]` line to the server console with session ID, classification, and elapsed time — visible in the `uvicorn` terminal output during this test run.
