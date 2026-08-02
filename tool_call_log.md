# Tool Call Log — Day 13

6 test questions run through `tool_calling_chat()`: 5 designed to each trigger a different tool (including one repeat tool with different arguments), and 1 designed to trigger no tool. All confirmed against the raw log in `tool_call_log_raw.json`.

## Results

### 1. "What are the plan details for P101?"
- **Tool called:** `get_plan_details`
- **Arguments:** `{"plan_id": "P101"}`
- **Result:** `{"plan_id": "P101", "plan_name": "Gold PPO", "monthly_premium": 500.0, "annual_deductible": 2000.0, "copay_pct": 10.0, "network_tier": "Gold"}`
- **Final answer:** Correctly summarized all 5 fields in natural language, ended with the required disclaimer.
- **Correct tool selected:** ✅

### 2. "What's the status of claim C1001?"
- **Tool called:** `get_claim_status`
- **Arguments:** `{"claim_id": "C1001"}`
- **Result:** `{"claim_id": "C1001", "status": "Pending", "procedure": "X-ray", "claim_amount": 250.0}`
- **Final answer:** Correctly reported status, procedure, and amount.
- **Correct tool selected:** ✅

### 3. "Is cosmetic surgery covered under plan P101?"
- **Tool called:** `check_coverage`
- **Arguments:** `{"plan_id": "P101", "procedure": "cosmetic surgery"}`
- **Result:** `{"plan_id": "P101", "procedure": "cosmetic surgery", "covered": false, "notes": "Excluded service per plan exclusions list."}`
- **Final answer:** Correctly reported cosmetic surgery as not covered, with an appropriate caveat to review the full plan document.
- **Correct tool selected:** ✅

### 4. "Estimate my out-of-pocket cost for a Surgery on plan P102."
- **Tool called:** `estimate_out_of_pocket_cost`
- **Arguments:** `{"plan_id": "P102", "procedure": "Surgery"}`
- **Result:** `{"procedure": "Surgery", "plan_id": "P102", "estimated_cost": 240.0, "notes": "Estimated as 20% of a $1200 mock base cost for Surgery."}`
- **Final answer:** Correctly reported $240, correctly flagged it as an estimate that may not include additional charges.
- **Correct tool selected:** ✅

### 5. "Does plan P103 cover an X-ray?"
- **Tool called:** `check_coverage` (second, distinct call — different plan and procedure from #3)
- **Arguments:** `{"plan_id": "P103", "procedure": "X-ray"}`
- **Result:** `{"plan_id": "P103", "procedure": "X-ray", "covered": true, "notes": "Not on the excluded services list (mock check; confirm with full policy for edge cases)."}`
- **Final answer:** Correctly reported X-ray as covered under P103.
- **Correct tool selected:** ✅

### 6. "What is health insurance in general?" (no-tool control question)
- **Tool called:** `None` — no tool call was made
- **Arguments:** `None`
- **Result:** `None`
- **Final answer:** Correctly declined to answer from outside knowledge, stating the tools don't provide a general definition, and directed the member to support.
- **Correct behavior (no tool triggered):** ✅

## Summary

**6/6 correct tool selections** — every question that should have triggered a tool triggered the *right* tool with the *right* arguments, and the control question correctly triggered no tool at all rather than forcing a spurious call. This includes two separate `check_coverage` calls (questions 3 and 5) with different plan/procedure argument pairs, confirming the model isn't just pattern-matching on the tool name but correctly extracting distinct arguments per question.

## Implementation notes

- All 4 tool functions are backed by Pydantic models (`CoverageCheckResult`, `ClaimStatusResult`, `PlanDetailsResult`, `OutOfPocketEstimate`) that validate every result's shape and types before it's serialized back to the model — malformed data from the database layer would raise a `ValidationError` and be caught, not silently passed through.
- `check_coverage` and `estimate_out_of_pocket_cost` use mock data (a hardcoded exclusions list matching `benefits.txt`, and a small base-cost lookup table) since Day 4's schema doesn't include a per-procedure coverage or pricing table. This is called out explicitly per Day 13's "mock data is fine" allowance.
- Nonexistent IDs (e.g. a claim or plan ID that doesn't exist) raise a `ValueError` inside the tool function, which is caught and returned to the model as an `{"error": "..."}` payload rather than crashing the pipeline — verified working during testing before the live run.
