# Retrieval Test Results — Day 10

10 test questions run through `retrieve()`, scored manually as a baseline for Day 11.

## Results

| # | Question | Classification | Retrieved Context (summary) | Score |
|---|---|---|---|---|
| 1 | What's my copay on the Gold PPO plan? | structured | SQL: Gold PPO, 10% copay | **Good** |
| 2 | Is maternity care covered on the Bronze plan? | unstructured | Exclusions clause (unrelated items), Medicaid comparison noise, Bronze plan summary, ER copay line — nothing about maternity | **Poor** |
| 3 | What's the status of claim C1001? | structured | SQL: Claim C1001, Pending, X-ray, $250 | **Good** |
| 4 | What is the deductible on the Silver plan? | structured | SQL: Silver HMO, $1500 deductible | **Good** |
| 5 | Are cosmetic surgeries excluded from coverage? | unstructured | Top result is the exact exclusions clause naming cosmetic surgery | **Good** |
| 6 | How much is the premium for the Bronze HMO plan? | structured | SQL: Bronze HMO, $150/mo | **Good** |
| 7 | What's the copay for the Gold PPO plan and is physical therapy covered? (mixed) | both | SQL correctly answers copay (10%); vector side returns plan summaries only, nothing on physical therapy | **Partial** |
| 8 | Is dental care covered for adults? | unstructured | Correct answer (adult dental excluded) present but ranked 4th, buried under unrelated Medicaid FAQ content | **Partial** |
| 9 | What's the status of claim C1003? | structured | SQL: Claim C1003, Denied, X-ray, $150 | **Good** |
| 10 | Does the Gold PPO plan cover routine eye care? | unstructured | Correct exclusions clause present, ranked 3rd of 5 | **Partial** |

## Score summary

- **Good:** 6/10
- **Partial:** 3/10
- **Poor:** 1/10

## Observations / retrieval misses

1. **Structured (SQL) retrieval is fully reliable** — every one of the 4 pure-structured questions and the structured half of the mixed question returned exactly correct data. The classifier's keyword rules correctly identified premium/deductible/copay/claim-status questions every time in this test set.

2. **Vector retrieval is accurate when the right chunk exists, but ranking is inconsistent.** In cases 5, 8, and 10, the *correct* exclusions clause was present in the top-5 results every time — but only ranked #1 once (case 5). In cases 8 and 10 it was buried at rank 3-4 behind unrelated FAQ-page content (Medicaid comparisons, eligibility tables) that happens to share vocabulary with the question but isn't actually relevant to our Gold PPO plan.

3. **Root cause of the ranking noise:** the knowledge base mixes two very different kinds of content — our actual synthetic plan documents (small, specific) and the scraped public Medicaid FAQ (large, generic, covers many topics broadly). Semantic search doesn't know one source is "our plan" and the other is "general reference," so generic Medicaid content competes for the same top-5 slots as our plan-specific exclusions text. A metadata filter (e.g. restricting to `source_file != faq_page.txt` for plan-specific questions) would likely fix cases 8 and 10.

4. **Genuine content gaps, not retrieval bugs:** case 2 (maternity) and half of case 7 (physical therapy) failed because the underlying documents never mention those topics at all — no amount of better ranking fixes a topic that was never ingested. This is a data-coverage problem, not a search-quality problem.

5. **Mixed classification (case 7) worked correctly at the routing level** — both `sql_lookup` and `vector_lookup` fired as expected, and results were merged/de-duplicated without errors. The partial score reflects incomplete underlying data, not a routing failure.

## Baseline for Day 11

- 6/10 good is a reasonable starting point, but the two clearest, cheapest wins are: (a) filter out `faq_page.txt` from plan-specific queries to fix ranking noise (cases 8, 10), and (b) flag when vector search returns no chunk under a reasonable distance threshold, so the system can say "not covered in our documentation" rather than returning irrelevant filler (case 2).
