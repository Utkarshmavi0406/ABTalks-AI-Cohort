# RAGAS Scorecard — Day 27

## A note on the library

`ragas` (both the latest release 0.4.3 and the community-recommended pinned fallback 0.3.9) currently fails to import at all in this environment: `ragas/llms/base.py` still imports `ChatVertexAI` from `langchain_community.chat_models.vertexai`, a path that no longer exists now that `langchain-community` has deprecated and removed that integration. This was verified as a genuine, currently open upstream bug (confirmed via a matching GitHub issue and reproduced identically on this machine, not specific to this project), not something fixable by picking a different version without risking breaking the working chatbot's `langchain`/`langgraph` dependencies from Days 21-24.

`ragas_run.py` implements the same 4 metrics as custom LLM-as-judge scoring functions instead — the same underlying technique RAGAS itself uses for these metrics, just without the broken import chain.

## Initial full run (18 questions)

| Metric | Average |
|---|---|
| faithfulness | 0.889 |
| answer_relevancy | 0.889 |
| context_precision | 0.804 |
| **context_recall** | **0.333** |

## Diagnosing the weakest metric

**context_recall (0.333) looked like the weakest metric, but the raw number is misleading** — it's largely a measurement-scope artifact, not a retrieval-quality defect. Every SQL-answered question (deductibles, claim statuses, premiums) automatically scored `recall=0.0`, because `score_context_recall()` only evaluates `retrieved_chunks` (vector-search results) — it has no visibility into SQL-sourced context at all. This isn't "chunk size too large" or "embedding model too weak" (the hypotheses the mission suggests as common causes) — it's that the metric literally cannot see half of what the pipeline retrieves.

**The real, actionable finding was hiding in a different place: faithfulness and answer_relevancy both scored 0.00 on exactly 2 of 18 questions** — "Which plan has the lowest monthly premium?" and "Which plan has the highest monthly premium?" — with a third question ("How does the Gold PPO plan's copay compare to the Bronze HMO plan's copay?") producing an incomplete answer that happened to score well on faithfulness/relevancy despite being wrong (it only reported one plan's copay, not both).

## Root cause (confirmed with actual evidence, not guessed)

Inspecting `ragas_results.json` showed `"retrieved_chunks": []` — **completely empty context** — for the two failing questions. Tracing through `retrieval_engine.py`:

1. `classify_question()` correctly detects "premium" as a structured-question keyword, routing the question to SQL-only lookup (never falling back to vector search).
2. `sql_lookup()` required a **specific plan name** to filter on via `_extract_plan_name()`.
3. Cross-plan comparison questions ("which plan has the **lowest** premium") don't name any single plan — they're asking about *all* plans at once.
4. With no plan name matched, `sql_lookup()` returned an empty list, and since the question was never routed to vector search either, the final context was completely empty.
5. The model correctly (from its own perspective) said "the context doesn't include this information" — faithful and relevant to what it actually had, which was nothing.

This is a genuine retrieval-routing gap: **the SQL layer had no path for cross-plan comparison/aggregation questions**, not a chunking or embedding problem.

## The fix

Modified `sql_lookup()` in `retrieval_engine.py`:
- Added `_extract_all_plan_names()` to find *every* plan name mentioned in a question, not just the first match (fixing the copay-comparison question, which named two plans but only ever got data for one).
- When a pricing question names no specific plan at all, `sql_lookup()` now returns **all plans' pricing data** instead of nothing, letting the LLM do the actual comparison.

Verified the fix directly against `sql_lookup()` in isolation before re-running the full pipeline — confirmed all 3 previously-broken questions now return complete data, with no regression on single-plan or claim-ID lookups.

## Before / after re-evaluation (3 affected questions)

| Question | Metric | Before | After |
|---|---|---|---|
| Lowest monthly premium | faithfulness | 0.00 | **1.00** |
| | answer_relevancy | 0.00 | **1.00** |
| | Answer | "The context provided does not include information..." | "The Bronze HMO has the lowest monthly premium at $150." (correct) |
| Highest monthly premium | faithfulness | 0.00 | **1.00** |
| | answer_relevancy | 0.00 | **1.00** |
| | Answer | "The answer isn't in the context..." | "The Gold PPO plan has the highest monthly premium at $500." (correct) |
| Gold PPO vs. Bronze HMO copay | Answer | "...does not include information about the Bronze HMO plan's copay" (incomplete, missing Bronze data) | "The Gold PPO plan's copay (10%) is lower than the Bronze HMO plan's copay (30%)." (complete and correct) |

**context_recall stayed at 0.00 after the fix** — this is expected and does **not** indicate the fix failed. It's the same SQL-blindness measurement limitation described above: the metric only checks vector-retrieved chunks, and these are (correctly) SQL-only questions with no vector chunks to evaluate. The SQL context itself is now genuinely complete and correct, confirmed by both the faithfulness/relevancy score jump and by manually reading the generated answers.

## Conclusion

The fix resolved the actual defect the evaluation surfaced: **faithfulness and answer_relevancy went from a hard 0.0 failure to a perfect 1.0 on both previously-broken questions**, and the third affected question now produces a complete, correct answer instead of an incomplete one. The context_recall metric's persistently low score across SQL-path questions is a known, documented limitation of this custom evaluation implementation (it can't see SQL context) rather than a signal of ongoing retrieval quality problems — a real RAGAS implementation, or a future improvement to this custom scorer, would need to account for SQL-sourced context as a distinct "ground truth source" alongside vector-retrieved chunks to measure recall meaningfully across the whole hybrid retrieval pipeline.
