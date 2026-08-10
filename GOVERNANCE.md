# Governance — AI Coverage Assistant

## Data sources used and their sensitivity

| Source | Contents | Sensitivity |
|---|---|---|
| `data/plans.csv` / `plans` table | Plan names, premiums, deductibles, copay %, network tier | Low — no individual-level data, purely product/pricing info |
| `data/claims.csv` / `claims` table | `claim_id`, `member_id`, `plan_id`, `procedure`, `claim_amount`, `status`, `date_filed` | **High** — `member_id` + `procedure` together constitute PHI (Protected Health Information) under HIPAA's definition, since they link an identifiable person to specific health services |
| `raw_text/enrollment.txt` (OCR'd) | Member name, date of birth, home address, phone, email, member ID | **High** — direct identifiers (name, DOB, address, contact info) combined with plan enrollment is squarely PHI |
| `raw_text/benefits.txt`, `claims_process.txt` | Policy language, exclusions, claims procedures | Low — no individual data, purely document text |
| `raw_text/faq_page.txt` | Scraped public Medicaid FAQ content | None — public, non-proprietary, no individual data |
| `coverage.db` `conversations` table (Day 20) | Full text of every member question and assistant answer, keyed by `session_id` | **High** — conversation content can incidentally contain anything a member types, including their own PHI shared in free text (e.g. "I'm member M1001 and I have a broken arm") |
| `chroma_data/` (vector store) | Embedded chunks of the above documents | Inherits the sensitivity of its source — the `plan_P101`-style structured chunks and any enrollment-derived chunks carry the same PHI concerns as their source data |

**Note:** all data in this project is synthetic/fake, generated for coursework (see Day 4-5 progress notes) — never real member data. This governance document is written as if it were describing a production system, per the mission's exercise framing, but the actual current dataset carries no real-world privacy risk.

## PHI/PII fields present

- **Direct identifiers:** member name (enrollment.txt only), date of birth, home address, phone, email
- **Indirect identifiers / quasi-identifiers:** `member_id` (e.g. `M1001`), `claim_id` (e.g. `C1001`) — not identifying on their own, but become PHI once linked to `procedure` and `claim_amount` in the same record
- **Health information:** `procedure` (e.g. "X-ray", "Surgery"), coverage/exclusion status for specific medical services
- **Financial information adjacent to health data:** `claim_amount`, `monthly_premium`, `annual_deductible` — not independently sensitive, but sensitive when tied to a specific member's specific claim

## Bias risks

- **Plan-tier assumptions:** the assistant could implicitly treat Bronze-tier members as less deserving of thorough answers if prompt or retrieval quality differs by plan (a real risk surfaced in this project's own testing — see the Day 10/22 findings that Bronze/Silver plans have far less detailed source documentation than Gold PPO, since only `benefits.txt` covers Gold PPO in depth). This is a genuine, measured bias risk, not hypothetical: a Bronze-plan member asking about coverage details today gets systematically thinner, less confident answers than a Gold-plan member asking the identical question, purely because of which plan's policy document happens to be more thoroughly represented in the knowledge base.
- **Procedure-type assumptions:** if certain procedures are more thoroughly documented or covered by better vector-search results than others, members asking about less-documented procedures could receive lower-quality guidance without any indication that the gap exists.
- **Language/phrasing bias:** the model's answer quality may vary based on how a question is phrased (e.g. "Is X covered?" vs. a more informal or non-native-English phrasing), which could disadvantage members who don't phrase questions in the style the retrieval/prompting pipeline was tuned against.

## Accountability for reviewing chatbot outputs

For this coursework project, there is no formal review process — this is a single-developer learning exercise. In a real deployment, the following would be minimum requirements (not currently implemented):

- A named compliance/privacy officer responsible for periodic audit of logged conversations (with PII redacted per Day 25's `redact_pii`) for accuracy, tone, and disclaimer compliance
- A clinical reviewer (not the engineering team) responsible for approving any language the assistant is allowed to use around medical topics, given the system prompt's explicit "not medical advice" boundary
- An incident process for when the assistant gives an incorrect answer about coverage or a claim, including a way for members to flag a bad answer and have it corrected

**This governance document and the guardrails/redaction built in this exercise are a learning exercise, not a substitute for a formal compliance review.** See "Production readiness note" below.

## Production readiness note (Step 7)

**Production use of this system would require a formal compliance review beyond what's implemented in this exercise.** Specifically, before handling any real member data, this project would need: a real HIPAA risk assessment, professional legal review of the disclaimer and data-handling language, penetration testing beyond the 5 adversarial prompts logged in `adversarial_tests.md`, a proper PII detection system (e.g. Presidio with NER, not the regex-based approach used here — see `redact_pii.py`'s documented limitations), audit logging with real access controls, and a Business Associate Agreement with any third-party model/hosting provider if PHI were ever sent to a non-local LLM. None of that exists today; this project is coursework, not a production-ready system.

**Specific gap found during adversarial testing (Test 5 in `adversarial_tests.md`):** a PHI-fishing question ("give me another member's name/address/phone") caused the retrieval layer to pull a chunk containing real PHI (a synthetic member's enrollment data) directly into the model's context. The final answer happened to be safe only because the model chose not to disclose it — no explicit guardrail currently prevents PHI-containing source chunks from being retrieved into context in the first place. A production system would need retrieval-layer filtering (e.g. excluding enrollment/PHI-tagged chunks from any query that doesn't reference the requesting member's own verified identity), not just output-side redaction after the fact.
