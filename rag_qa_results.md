# RAG QA Results — Day 11

Full pipeline (`retrieve_and_answer`) run against the same 10 Day 10 test questions, using Ollama (`qwen3:8b`) with a grounding prompt restricting answers to retrieved context only.

## Results

| # | Question | Classification | Final Answer | Day 10 Score | Day 11 Score |
|---|---|---|---|---|---|
| 1 | What's my copay on the Gold PPO plan? | structured | "The copay for the Gold PPO plan is 10%." | Good | **Good** |
| 2 | Is maternity care covered on the Bronze plan? | unstructured | Correctly states maternity coverage is not explicitly confirmed in context; suggests contacting support | Poor | **Good** |
| 3 | What's the status of claim C1001? | structured | "Pending" | Good | **Good** |
| 4 | What is the deductible on the Silver plan? | structured | "$1500" | Good | **Good** |
| 5 | Are cosmetic surgeries excluded from coverage? | unstructured | "Yes, cosmetic surgery is excluded from coverage" | Good | **Good** |
| 6 | How much is the premium for the Bronze HMO plan? | structured | "$150 per month" | Good | **Good** |
| 7 | Copay for Gold PPO + is physical therapy covered? (mixed) | both | Correctly answers copay (10%); correctly says physical therapy not specified, suggests contacting support | Partial | **Good** |
| 8 | Is dental care covered for adults? | unstructured | Surfaces "adult dental care is excluded" but blends it confusingly with generic Medicaid policy text from the unrelated FAQ scrape, implying state-by-state Medicaid rules apply to the member's actual plan | Partial | **Partial** |
| 9 | What's the status of claim C1003? | structured | "Denied" | Good | **Good** |
| 10 | Does the Gold PPO plan cover routine eye care? | unstructured | "No, the Gold PPO plan does not cover routine eye care" | Partial | **Good** |

## Score summary

- **Good:** 9/10 (up from 6/10 in Day 10)
- **Partial:** 1/10 (down from 3/10)
- **Poor:** 0/10 (down from 1/10)

## Comparison against Day 10 baseline

**Are answers correct, well-formed sentences (not raw chunks)?**
Yes, across the board. Every Day 11 answer is a clean, direct sentence rather than a raw SQL string or a truncated 300-character text chunk. This is the clearest improvement over Day 10 — even the structured (SQL) answers, which were already factually correct in Day 10, read far better as natural sentences ("The status of claim C1001 is Pending" vs. the raw `[SQL] Claim C1001: status=Pending, procedure=X-ray, amount=$250`).

**Do they avoid overstating coverage that isn't clearly confirmed?**
Mostly yes, and this is the more important win. The grounding prompt's instruction to say "I don't know" when the context doesn't contain the answer worked correctly on both cases where Day 10 had no relevant data (maternity, physical therapy) — the model explicitly declined to guess and recommended contacting support, rather than fabricating a plausible-sounding but ungrounded answer. This is exactly the safety behavior the prompt was designed to produce for a health coverage assistant.

**The one remaining issue (case 8) is a new kind of risk, not the same old one.** In Day 10, the "dental" question surfaced the correct fact buried under obviously irrelevant raw FAQ text — a member reading five disconnected block-quotes would likely notice the noise and be skeptical. In Day 11, the LLM smooths that same noisy context into fluent, confident-sounding prose that blends unrelated general Medicaid policy with the member's actual (unrelated) plan. The underlying fact (adult dental excluded) is still correct, but the surrounding sentences could mislead a member into thinking state Medicaid rules apply to their private plan. **Fluent wrong-context blending is arguably more dangerous than raw noisy chunks**, because it's harder for a non-expert reader to spot that the source material was mismatched. This traces back to the same root cause flagged in Day 10: the FAQ scrape (`faq_page.txt`) competing for retrieval slots against plan-specific content it has no real relevance to.

## Recommendation for future iteration

Filtering `faq_page.txt` out of retrieval for plan-specific questions (as noted in the Day 10 baseline) becomes more urgent after this test, not less — the LLM's fluency makes bad context look more trustworthy, not less.