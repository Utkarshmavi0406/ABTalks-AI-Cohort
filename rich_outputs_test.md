# Rich Outputs Test — Day 19

Three test questions run through the full Day 19 pipeline (citations + structured cards), confirmed against live screenshots of the running app.

## Test 1 — Citations

**Question:** "Is cosmetic surgery excluded from coverage?"

**Expected:** A "Policy sources" section listing the chunk IDs the answer was grounded on.

**Result:** ✅ Confirmed. The assistant answered "Yes, cosmetic surgery is excluded from coverage as stated in the context," and an expandable "Policy sources (5)" section appeared underneath listing:
- `benefits_chunk_5`
- `faq_page_chunk_25`
- `faq_page_chunk_7`
- `faq_page_chunk_26`
- `benefits_chunk_6`

**Note:** this also confirms a known issue documented back in the Day 10 retrieval baseline — the citation list mixes the actually-relevant `benefits_chunk_*` sources with irrelevant `faq_page_chunk_*` content pulled in from the general Medicaid FAQ scrape. The citation feature is working correctly as a transparency mechanism; it's now also visibly surfacing the retrieval noise issue to the end user, which is arguably a feature in itself (a member could see the sources are mixed-quality) but also strengthens the case for filtering `faq_page.txt` out of plan-specific queries, as previously recommended.

## Test 2 — Claim-status card

**Question:** "What is the status of claim C1001?"

**Expected:** A `ClaimStatusCard` rendered with claim ID, status, amount, and date.

**Result:** ✅ Confirmed. Card rendered with:
- Claim C1001
- Status: **Pending**
- Amount: **$250.00**
- Date filed: **2023-04-01**

Matches the underlying `coverage.db` record exactly. Rendered as `st.metric` columns inside a bordered container, not raw text.

## Test 3 — Coverage-summary card

**Question:** "Is cosmetic surgery covered under the Gold PPO plan?"

**Expected:** A `CoverageSummaryCard` showing plan name, deductible, copay, and covered status.

**Result:** ✅ Confirmed. Card rendered with:
- Gold PPO — Coverage Summary
- Deductible: **$2,000**
- Copay: **10%**
- Covered: **❌ No**

Correctly reflects that cosmetic surgery is on the plan's exclusions list. This question also correctly triggered both the card *and* a citations expander (5 sources), confirming the two rich-output features work together on the same response rather than being mutually exclusive.

## Markdown rendering (Step 5)

Confirmed via `st.markdown()` inside `st.chat_message` — this is native Streamlit behavior that renders lists, tables, and code blocks automatically without any Day 19 code changes needed. Visually verified in the above screenshots that the assistant's text renders with correct **bold** formatting (e.g. "does **not** cover") produced by the LLM's markdown output.

## Summary

All 3 required test cases pass:
- ✅ Citations render correctly as an expandable "Policy sources" section
- ✅ Claim-status card renders correctly with accurate data
- ✅ Coverage-summary card renders correctly with accurate data
- ✅ Cards and citations can co-occur on the same answer without conflict
