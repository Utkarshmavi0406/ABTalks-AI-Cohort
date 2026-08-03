# Streaming Notes — Day 18

## Protocol

`/chat` now returns `text/event-stream` (SSE) instead of a single JSON body. Each event is a line of the form:

```
data: <content>\n\n
```

- Each token from the LLM is sent as its own `data:` line as soon as it's generated.
- Raw newlines inside a token are escaped as `\n` (literal backslash-n) before sending, since SSE payloads can't contain unescaped newlines within a single event — the client un-escapes them back to real newlines on receipt.
- A sentinel `data: [DONE]\n\n` marks the end of the stream, always sent exactly once, in a `finally` block, regardless of whether the stream succeeded or failed partway.
- A sentinel prefix `[ERROR]` marks a failure message meant to be shown to the user directly, distinguishing it from a normal token.

## Server-side error handling (Step 6)

Two separate failure points are handled in `main.py`'s `/chat` generator:

1. **Retrieval failure** (before any tokens are sent): if `retrieve()` raises an exception, the generator yields a single `[ERROR]` event with a user-facing message, then `[DONE]`, and returns — no partial stream was ever started, so there's nothing to clean up.

2. **Mid-stream failure** (after some tokens have already been sent, e.g. the local Ollama connection drops or a request to it times out): the `for token in generate_answer_stream(...)` loop is wrapped in a try/except. On failure, the generator yields an `[ERROR]` event with a message explaining the connection was lost, then falls through to the `finally` block, which always logs whatever partial answer was accumulated (if any) to the session store and sends `[DONE]`.

Every request also logs a `[TIMING]` line to the server console (session ID, classification, elapsed time) and every completed or partial answer is still saved to `SESSION_STORE`, so `/history` reflects what the member actually saw — including a failed attempt's partial text, if any tokens made it through before the drop.

## Client-side (Streamlit) error handling

- `requests.post(..., stream=True, timeout=(5, 90))` sets a 5-second connect timeout and a 90-second read timeout. If the backend never responds at all, or stalls for more than 90 seconds between chunks, `requests` raises a `RequestException`.
- This is caught around the whole streaming loop; on any such exception, the placeholder is updated with a friendly message ("Sorry, I lost connection to the coverage backend. Please try again.") instead of leaving a half-typed answer hanging with no explanation.
- If the server sends its own `[ERROR]` event (the two server-side cases above), the client detects the `[ERROR]` prefix and displays that message directly rather than treating it as regular streamed text.
- If the stream ends with `[DONE]` but zero tokens were ever received (an edge case, e.g. an empty response), the client falls back to a generic "didn't get a response" message rather than showing a blank chat bubble.

## UX behavior

- A "_Thinking..._" placeholder shows immediately after the user sends a message, before the first token arrives (Step 5).
- Once tokens start arriving, each one is appended to the same placeholder with a trailing cursor character (`▌`) to visibly simulate typing, satisfying Step 4's "should visibly type out, not wait for the full answer."
- The cursor is removed on the final render once the stream completes (or errors out) so the finished message doesn't have a stray trailing character.
