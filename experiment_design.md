# Experiment Design — Prompt Variant A vs. Variant E

## Variants under test

- **Variant A (strict)** — Day 12's strict/formal system prompt. Cites exact plan terms, refuses anything resembling medical advice outright, no mandated disclaimer on every answer.
- **Variant E (hybrid)** — Day 12's winning hybrid system prompt. Same grounding discipline as A, plus a mandatory closing disclaimer on every single answer and slightly warmer phrasing.

Chosen because Day 12's original 5-question test already found Variant E scored highest on compliance (consistent disclaimer usage) while matching A on accuracy — this experiment re-tests that finding at 3x the sample size (15 vs. 5 questions) to see if it holds up, rather than assuming a 5-question result generalizes.

## Hypothesis

Variant E will show a higher rate of "good" answers than Variant A, primarily driven by more consistent disclaimer inclusion — not because E is more factually accurate (both variants use the same underlying retrieval and grounding context), but because E's explicit "end every answer with the disclaimer" instruction removes an inconsistency Variant A is prone to.

## Metric

**% of answers rated "good"** out of 15, scored manually against three criteria: (1) factually correct given the retrieved context, (2) includes the required disclaimer, (3) doesn't fabricate detail beyond the retrieved context. An answer is "good" only if all three hold; otherwise "partial" (1-2 hold) or "poor" (0 hold).

## Sample size

**15 questions**, covering a mix of structured lookups (copay, deductible, premium, claim status), unstructured/coverage-exclusion questions, and at least one question with no answer available in the knowledge base (to test appropriate "I don't know" behavior under both variants).

## Decision rule

- If Variant E's good-rate exceeds Variant A's by **more than 20 percentage points** (i.e., 3+ more "good" answers out of 15): adopt E as the production system prompt with confidence.
- If the difference is **10-20 percentage points**: lean toward E, but note the sample size (15) is small enough that this could be noise — recommend a larger follow-up test before fully committing.
- If the difference is **under 10 percentage points**: treat as inconclusive at this sample size; either variant is acceptable, and the choice should be made on other grounds (e.g. Variant E's mandatory disclaimer is a compliance requirement regardless of measured accuracy difference).

This decision rule is deliberately conservative given how small a 15-question sample is — a few-point difference could easily be within normal run-to-run noise for a single local LLM, and the rule accounts for that rather than treating any nonzero gap as meaningful.
