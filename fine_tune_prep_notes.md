# Fine-Tune Prep Notes — Day 14

## Step 1: Recurring issues from Day 10-13 test logs

### Issue 1 — Inconsistent disclaimer usage (FINE-TUNING CAN FIX)
Across Day 12's prompt variants (`prompt_variants.md`), only Variant E consistently appended "This is not medical advice" to every answer. Variants C and D only included it when the question happened to match a "missing information" pattern — simple factual answers (copay, deductible lookups) frequently had no disclaimer at all. This is a behavioral consistency problem: the model *can* produce the right disclaimer, it just doesn't reliably do so across all answer types when relying on prompt instructions alone. Fine-tuning on examples where every single answer — regardless of complexity — ends with the disclaimer would bake this in as a learned pattern rather than something the model has to be reminded of via system prompt every time.

### Issue 2 — Overstating/speculating beyond retrieved context (FINE-TUNING CAN FIX)
In Day 12's testing, Variant B (empathetic) added an unsupported elaboration on a simple copay question — "e.g., for healthcare services or prescriptions, depending on the plan's structure" — details not present anywhere in the actual context. This happened specifically because the model was trying to sound more helpful/complete, and drifted into filling gaps with plausible-sounding but ungrounded detail. Fine-tuning on curated examples that consistently stop exactly at what the context supports (no elaboration, no filling in "reasonable" extra detail) would reinforce strict grounding as the default behavior rather than something the model has to be told not to do.

### Issue 3 — FAQ-page noise polluting plan-specific answers (RETRIEVAL PROBLEM — FINE-TUNING WILL NOT FIX)
Across Day 10 and Day 11 testing, questions about dental coverage and routine eye care consistently pulled in irrelevant general Medicaid policy text from the scraped `faq_page.txt` source, alongside the actually-relevant plan exclusion clause. Every single Day 12 prompt variant exhibited this same blending problem on the dental question, regardless of tone or instruction style — because the underlying *retrieved context itself* was already contaminated with off-topic content before the model ever saw it. No amount of output-style training changes what gets retrieved and handed to the model as input; this needs a retrieval-layer fix (e.g., filtering `faq_page.txt` out of plan-specific queries, or better metadata-based scoping), not a fine-tuning fix.

## Summary

| Issue | Fine-tuning fixes it? | Why |
|---|---|---|
| Inconsistent disclaimer usage | Yes | Behavioral/output-style pattern — exactly what fine-tuning is good at reinforcing |
| Overstating beyond context | Yes | Also a behavioral pattern — training the model to stop exactly at grounded facts |
| FAQ-page noise polluting answers | No | Retrieval/data problem — the input context itself is wrong; no output-style training fixes bad input |

This tracks with the mission's framing: fine-tuning helps with *consistent tone, correct disclaimer usage, and domain terminology* — not with *new factual knowledge* or, by extension, *fixing what gets retrieved in the first place*.
