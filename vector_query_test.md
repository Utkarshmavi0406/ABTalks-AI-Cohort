# Vector Query Test — Day 9

## Setup
- Collection: `coverage_kb` (Chroma, persistent local store)
- Chunk count upserted: 51 (matches `knowledge_base.jsonl` exactly)
- Query text: *"Is physical therapy covered under the Silver plan?"*
- Embedding model: `all-MiniLM-L6-v2`

## Unfiltered query (n_results=5)

| Rank | id | plan_type | section | distance | Relevant? |
|---|---|---|---|---|---|
| 1 | benefits_chunk_5 | Gold PPO | exclusions | 0.9152 | No — wrong plan |
| 2 | benefits_chunk_0 | Gold PPO | coverage | 1.1291 | No — wrong plan, header only |
| 3 | enrollment_chunk_0 | general | enrollment | 1.1299 | No — unrelated content |
| 4 | plan_P102 | Silver HMO | coverage | 1.1661 | **Yes — only relevant result** |
| 5 | benefits_chunk_6 | Gold PPO | coverage | 1.2608 | No — wrong plan |

**Observations:**
- Only 1 of the top 5 unfiltered results is actually about the Silver plan, and it ranks 4th, not 1st.
- The top-ranked result is Gold PPO's exclusions text — likely surfaced because that section contains therapy-adjacent terms (chiropractic, physical therapy-related exclusions), even though it describes the wrong plan entirely.
- **Root cause:** the knowledge base has detailed multi-paragraph policy text only for Gold PPO (from `benefits.txt`). Silver HMO exists only as a single one-line structured summary (`plan_P102`) with no equivalent detailed benefits document. Semantic similarity naturally favors the richer, more topically-detailed Gold PPO text over the sparse Silver HMO record.
- **This is a genuine retrieval miss** caused by uneven source coverage across plans, not a bug in the embedding or query pipeline.

## Filtered query (n_results=5, where plan_type="Silver HMO")

| Rank | id | plan_type | section | distance |
|---|---|---|---|---|
| 1 | plan_P102 | Silver HMO | coverage | 1.1661 |

**Observations:**
- The metadata filter correctly scoped results to exactly one record — the only chunk in the knowledge base tagged `plan_type: Silver HMO`.
- No Gold PPO content leaked through — the `where` filter works as expected.
- Filtering **fixes the precision problem** (no wrong-plan content returned) but can't fix a **coverage gap** — there simply isn't a detailed Silver HMO benefits document to retrieve, so the filtered result is thin (one summary line, no exclusions/coverage detail comparable to Gold PPO).

## Filtered vs. unfiltered — summary

Metadata filtering is essential for plan-specific questions: it eliminates cross-plan contamination that the unfiltered query clearly suffered from (4 of 5 top results were wrong-plan). However, filtering exposes rather than solves the underlying gap — Silver HMO and Bronze HMO both lack detailed policy documents in this synthetic dataset, so filtered queries for those plans will only ever return the thin one-line plan summary. A production version of this knowledge base would need equivalent SBC-style documents ingested for every plan, not just Gold PPO, for filtered retrieval to be genuinely useful across all three plans.