# Multi-Agent Comparison — Day 22

Same 5 test questions from Day 21, run through the multi-agent Router + Coverage Specialist + Claims Specialist workflow, compared against the Day 21 single-agent baseline.

## Architecture

- **Router**: LLM call classifies each question into `coverage`, `claims`, or `enrollment`, then dispatches to the matching specialist.
- **Coverage Specialist**: a tool-calling agent scoped to `check_coverage` and `get_plan_details` — same tools Day 21's single agent had, just owned by a dedicated node.
- **Claims Specialist**: extracts a claim ID directly and calls `get_claim_status()` deterministically — a genuinely different code path than Coverage Specialist, not just a relabeled copy.
- **Enrollment**: has no dedicated specialist (no structured enrollment data exists beyond one raw text chunk); falls back to Coverage Specialist. Documented as a known gap, not silently hidden.

## First attempt: a real finding worth keeping in this record

The first version of the Coverage Specialist used Day 10's RAG pipeline (`retrieve()` + `generate_answer()`) instead of tools. It **failed on 3 of 4 non-claims questions** — not because multi-agent routing was broken, but because the underlying knowledge base's text chunks only ever mention plan **names** ("Gold PPO"), never plan **IDs** ("P101"). The strict grounding prompt correctly refused to assert "P101 = Gold PPO" since that mapping only exists in metadata, invisible to the model. Day 21's tool-calling agent never hit this problem because `get_plan_details(plan_id="P101")` queries the database directly by ID — no text-matching required at all.

**This is the single most important finding from today**: multi-agent orchestration doesn't automatically improve answer quality — the quality still depends entirely on what each specialist is built on. A specialist wrapping a weaker retrieval mechanism will underperform a well-tooled single agent, even if the routing itself is perfect.

## Second attempt: Coverage Specialist rebuilt with tool access

Once Coverage Specialist was rebuilt to use the same `check_coverage`/`get_plan_details` tools as Day 21 (rather than pure RAG), all 5 questions passed cleanly.

| # | Question | Router decision | Specialist | Tool called | Result vs. Day 21 |
|---|---|---|---|---|---|
| 1 | Plan details for P101 | coverage | Coverage | `get_plan_details({'plan_id': 'P101'})` | ✅ Identical answer quality |
| 2 | Status of claim C1001 | claims | Claims | `get_claim_status('C1001')` | ✅ Identical |
| 3 | Cosmetic surgery covered under P101? | coverage | Coverage | `check_coverage({'plan_id': 'P101', 'procedure': 'cosmetic surgery'})` | ✅ Identical |
| 4 | Does P103 cover an X-ray? | coverage | Coverage | `check_coverage({'plan_id': 'P103', 'procedure': 'X-ray'})` | ✅ Identical |
| 5 | General health insurance question | coverage (fallback) | Coverage | none | ✅ Identical — correctly answered directly, offered to look up specifics |

**Routing accuracy: 5/5 correct.** **Answer quality: matches Day 21 exactly on all 5 questions**, once Coverage Specialist had equivalent tooling.

## Step 6: When is multi-agent worth it?

**Multi-agent helped here in one concrete way**: the Claims Specialist's deterministic, non-LLM-driven claim lookup (extract ID → direct DB query) is simpler and more auditable in isolation than folding claims logic into a single agent's larger tool list. If claims and coverage logic diverge further in the future (e.g. claims gaining approval workflows, appeals, multi-step processes), having a dedicated Claims Specialist gives a clean place to grow that complexity without bloating a single agent's toolset or system prompt.

**Multi-agent did not improve answer quality on these 5 questions** — once both specialists had equivalent tools to Day 21's single agent, results were identical. The router added a real architectural seam (domain-level dispatch, distinct from Day 10's mechanism-level SQL-vs-vector routing) but no measurable quality gain for this test set, because these 5 questions don't actually require cross-domain reasoning — each one cleanly belongs to exactly one domain.

**General conclusion:**
- **Genuinely different domains with different data/tooling needs** (here: claims' deterministic ID lookups vs. coverage's semantic/tool-based lookups) → multi-agent is a reasonable structural choice, mainly for maintainability and separation of concerns as each domain grows in complexity, not because it inherently produces better single-question answers.
- **Simple or single-domain questions, or a small tool set that one agent can hold entirely** → a single well-tooled agent (Day 21's approach) is simpler to build, debug, and reason about, with no proven quality disadvantage in this test.
- **The real risk with multi-agent**: a specialist accidentally built on a weaker underlying mechanism than a single agent would have had — exactly what happened here on the first attempt. Splitting into specialists doesn't automatically preserve capability; each specialist needs to be verified independently, not assumed equivalent just because it's "specialized."
