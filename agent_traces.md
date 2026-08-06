# Agent Traces — Day 21

5 test questions run through the LangChain ReAct-style agent (`create_agent`, built on LangGraph, wrapping the Day 13 tools). Traces reconstructed from the agent's returned message list since `create_agent` uses native tool-calling rather than the classic text-parsed ReAct format.

## Setup note

`create_react_agent` / `AgentExecutor` (referenced in the mission instructions) are the LangChain 0.x agent API. The installed version (`langchain` 1.3.14) replaced these with a unified `create_agent`, built on LangGraph, that performs the same reasoning-loop-with-tools behavior via native LLM tool-calling rather than text-parsed ReAct prompting. Since this doesn't print classic `Thought/Action/Observation` traces automatically, `langchain_agent.py` reconstructs that format from the agent's structured message output (`AIMessage` tool calls → "Action", `ToolMessage` → "Observation", final `AIMessage` → "Final Answer").

## Trace 1: "What are the plan details for P101?"

```
Thought: I need to look this up using a tool.
Action: get_plan_details
Action Input: {'plan_id': 'P101'}
Observation: {"plan_id": "P101", "plan_name": "Gold PPO", "monthly_premium": 500.0, "annual_deductible": 2000.0, "copay_pct": 10.0, "network_tier": "Gold"}
Thought: I now know the final answer.
Final Answer: The plan details for P101 (Gold PPO)...
```
**Tool selection:** ✅ Correct — `get_plan_details` with the right `plan_id`.

## Trace 2: "What's the status of claim C1001?"

```
Thought: I need to look this up using a tool.
Action: get_claim_status
Action Input: {'claim_id': 'C1001'}
Observation: {"claim_id": "C1001", "status": "Pending", "procedure": "X-ray", "claim_amount": 250.0}
Thought: I now know the final answer.
Final Answer: The status of claim C1001 is Pending...
```
**Tool selection:** ✅ Correct — `get_claim_status` with the right `claim_id`.

## Trace 3: "Is cosmetic surgery covered under plan P101?"

```
Thought: I need to look this up using a tool.
Action: check_coverage
Action Input: {'plan_id': 'P101', 'procedure': 'cosmetic surgery'}
Observation: {"plan_id": "P101", "procedure": "cosmetic surgery", "covered": false, "notes": "Excluded service per plan exclusions list."}
Thought: I now know the final answer.
Final Answer: Cosmetic surgery is not covered under plan P101...
```
**Tool selection:** ✅ Correct — `check_coverage` with correct plan and procedure arguments.

## Trace 4: "Does plan P103 cover an X-ray?"

```
Thought: I need to look this up using a tool.
Action: check_coverage
Action Input: {'plan_id': 'P103', 'procedure': 'X-ray'}
Observation: {"plan_id": "P103", "procedure": "X-ray", "covered": true, "notes": "Not on the excluded services list (mock check; confirm with full policy for edge cases)."}
Thought: I now know the final answer.
Final Answer: Plan P103 does cover X-rays...
```
**Tool selection:** ✅ Correct — a second, independent `check_coverage` call with genuinely different arguments (not reused from Trace 3), confirming the agent extracts arguments per-question rather than pattern-matching on the tool name alone.

## Trace 5: "What is health insurance in general?"

```
Thought: I now know the final answer.
Final Answer: Health insurance is a type of insurance that covers the cost of medical services...
```
**Tool selection:** ✅ Correct — no tool called. The agent correctly recognized this as a general knowledge question with no specific plan/claim to look up, and answered directly.

## Step 5: Comparison to a human coverage-support rep

| # | Question | Agent's tool choice | Matches what a human rep would do? |
|---|---|---|---|
| 1 | Plan details | `get_plan_details` | ✅ Yes — a rep pulls up the plan record |
| 2 | Claim status | `get_claim_status` | ✅ Yes — a rep looks up the claim by ID |
| 3 | Coverage check (P101) | `check_coverage` | ✅ Yes — a rep checks the exclusions list |
| 4 | Coverage check (P103) | `check_coverage` | ✅ Yes — same action, different plan |
| 5 | General question | No tool | ✅ Yes — a rep also wouldn't pull a specific record for a general question |

**No wrong tool selections. No cases of a tool firing when it shouldn't have, or failing to fire when it should have.** All 5 test questions produced exactly the tool-selection behavior a human coverage-support rep would exhibit.

**Minor observation, not a failure:** on Trace 4, a thorough human rep might add a stronger caveat about edge cases. The agent's final answer did include a version of this caveat, echoing the tool's own `notes` field ("mock check; confirm with full policy for edge cases"), so this is more a consistency note than an actual gap.

## Conclusion

5/5 correct tool selections, matching human-rep behavior on every test case, including a genuine test of argument-extraction accuracy (two separate `check_coverage` calls with distinct plan/procedure pairs). No further tuning needed based on this test set.
