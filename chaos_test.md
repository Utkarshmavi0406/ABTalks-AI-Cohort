# Chaos Test — Day 24

## Setup

`multi_agent.py`'s Coverage/Claims Specialists now call MCP tools over the real protocol (via `stdio_client` + `ClientSession`, connecting to `mcp_server.py` as a subprocess), instead of Day 22's direct Python function imports. Every tool call goes through `call_tool_resilient()`: a 10-second timeout (`asyncio.wait_for`), one retry on failure, then a canned fallback message ("I'm having trouble accessing that right now, please contact member support") — never a raw crash or exception surfaced to the member.

## A bug found before the chaos test even started

The first attempt at breaking `check_coverage` (renaming its `@mcp.tool(name=...)` to `check_coverage_BROKEN`) produced output that *looked* like graceful degradation — sensible "I don't have access" answers, no crash — but **none of the `[MCP TOOL] ... failed` log lines appeared**. Investigating why revealed a real bug: `mcp`'s `CallToolResult` signals a tool-side failure (like calling an unknown tool name) via an `is_error` boolean field, **not by raising a Python exception**. The original `call_tool_resilient()` only had a `try/except` around the call and never checked `is_error` — so a failed tool call was silently treated as a *successful* one, and its error text ("Unknown tool: check_coverage") got passed straight to the LLM as if it were real data. The LLM happened to synthesize a plausible-sounding response from that error text, which is why it looked fine, but the actual designed resilience logic (Step 3/4's timeout + retry + fallback) never engaged at all.

**Fix:** added an explicit check —
```python
if getattr(result, "is_error", False):
    raise RuntimeError(f"Tool returned an error result: {result.content}")
```
— so an error result now correctly flows into the same retry/fallback path as a raised exception. Verified with a unit-style test simulating an `is_error=True` result before re-running the real chaos test.

## Chaos test (with the fix in place)

**Break applied:** renamed `check_coverage`'s tool registration in `mcp_server.py` to `check_coverage_BROKEN`, so `multi_agent.py` (which still calls `"check_coverage"`) can no longer find it on the server.

**Result — all 5 test questions, script run end to end:**

| # | Question | Domain | Tool called | Result |
|---|---|---|---|---|
| 1 | Plan details for Gold PPO | coverage | `check_coverage` (broken) | 2 failed attempts logged, then fallback-flavored answer: *"...currently unavailable due to a system issue. Please contact member support..."* |
| 2 | Status of claim C1001 | claims | `get_claim_status` (untouched) | ✅ Unaffected — correct answer, no errors |
| 3 | Cosmetic surgery under P101 | coverage | `check_coverage` (broken) | 2 failed attempts logged, graceful fallback-flavored answer |
| 4 | Does P103 cover X-ray | coverage | `check_coverage` (broken) | 2 failed attempts logged, graceful fallback-flavored answer |
| 5 | General health insurance question | coverage | `check_coverage` (broken, though not strictly needed for this question) | 2 failed attempts logged, but still answered reasonably from general knowledge |

**Confirmed:**
- ✅ Script completed all 5 questions without crashing
- ✅ Every failed `check_coverage` call showed exactly 2 attempts (1 initial + `MAX_RETRIES=1`) before falling back, matching the configured resilience settings
- ✅ No raw exception or 500-style error ever reached the "member" (the final printed answer)
- ✅ Claims Specialist was completely unaffected by the coverage tool breaking — confirming good isolation between specialists
- ✅ Each fallback naturally incorporated "contact member support" language, appropriate for a real degraded-service response

## Step 6: Fix reverted, normal operation confirmed

Renamed `check_coverage_BROKEN` back to `check_coverage` in `mcp_server.py`. Re-ran the same 5 questions — output was byte-for-byte consistent with the original pre-break run: real plan data, real coverage determinations, zero `[MCP TOOL] ... failed` lines. System fully restored.

## Known limitation (documented, not fixed today)

During initial testing (before the chaos test), question 4 ("Does plan P103 cover an X-ray?") returned **incorrect dollar amounts** — it answered with Gold PPO's $2,000 deductible / 10% copay instead of Bronze HMO's actual $1,000 deductible / 30% copay. Root cause: the question references the plan by **ID** ("P103"), but the plan-extraction regex only recognizes plan **names** ("Gold PPO", "Silver HMO", "Bronze HMO"). When no name matches, the code falls back to Day 20's remembered plan from earlier in the conversation (Gold PPO, from question 1) — which is the wrong plan for a question explicitly asking about a different one by ID. This is a real correctness issue (same root cause as the finding documented in Day 22's `multi_agent_comparison.md`), left undone today since today's scope was MCP integration + memory + resilience, not fixing plan-ID resolution. Flagged here for future work: add a plan-ID-to-name lookup via the `plans` table so ID-based questions resolve correctly instead of silently falling back to a stale remembered plan.
