# A/B Test Results — Variant A vs. Variant E

15 questions, each scored against three criteria: (1) factually correct given retrieved context, (2) includes the disclaimer, (3) no fabrication beyond context. **Good** = all 3 hold. **Partial** = 1-2 hold. **Poor** = 0 hold.

## Scored results

| # | Question | Variant A | Score A | Variant E | Score E |
|---|---|---|---|---|---|
| 1 | Copay Gold PPO | Correct, no disclaimer | Partial | Correct + disclaimer | Good |
| 2 | Claim C1001 status | Correct, no disclaimer | Partial | Correct + accurate detail + disclaimer | Good |
| 3 | Cosmetic surgery excluded | Correct, no disclaimer | Partial | Correct + disclaimer | Good |
| 4 | Deductible Silver HMO | Correct, no disclaimer | Partial | Correct + disclaimer | Good |
| 5 | Premium Bronze HMO | Correct, no disclaimer | Partial | Correct + disclaimer | Good |
| 6 | Dental care adults | Correct-to-context, no disclaimer | Partial | Correct-to-context + disclaimer | Good |
| 7 | Claim C1003 status | Correct, no disclaimer | Partial | Correct + disclaimer | Good |
| 8 | Gold PPO eye care | Correct, but **leaked an internal `[VECTOR:exclusions]` tag into the member-facing answer** — no disclaimer | Partial | Correct + disclaimer, no leaked tags | Good |
| 9 | X-ray out-of-pocket cost | Correctly declines, no disclaimer | Partial | Correctly declines + disclaimer | Good |
| 10 | Physical therapy covered | Correctly declines, no disclaimer | Partial | Correctly declines + disclaimer | Good |
| 11 | Claim C1004 status | Correct, no disclaimer | Partial | Correct + accurate detail + disclaimer | Good |
| 12 | Private-duty nursing | **Self-contradicting, broken response** — states "not covered," then "I don't have that information," then "Correction: ... The second response was an error." No disclaimer. | **Poor** | Correct + disclaimer, but adds "unless specifically added through a separate long-term care policy" — **not stated anywhere in the retrieved context**, a genuine fabrication | Partial |
| 13 | Weight loss coverage | Correct, no disclaimer | Partial | Correct + disclaimer | Good |
| 14 | Claim C1005 status | Correct, no disclaimer | Partial | Correct + disclaimer | Good |
| 15 | Acupuncture covered | Correct, no disclaimer | Partial | Correct core fact + disclaimer, though mislabels the section as part of "the exclusions" (it's actually the separate "Other Covered Services" section) | Good |

## Tabulated results

| | Good | Partial | Poor | Good rate |
|---|---|---|---|---|
| **Variant A** | 0 | 14 | 1 | **0%** |
| **Variant E** | 14 | 1 | 0 | **93.3%** |

## Which variant wins, and by how much

**Variant E wins decisively — 93.3 percentage points higher good-rate (93.3% vs. 0%).** Per the decision rule in `experiment_design.md` (adopt with confidence if the gap exceeds 20 points), this is an unambiguous result: **adopt Variant E** as the production system prompt.

## Is the difference meaningful given the small sample size?

**Yes, and here's why this result is trustworthy despite only 15 questions:** the gap isn't a marginal, noise-prone difference — it's driven almost entirely by one binary, deterministic factor: **Variant A's system prompt never mandates a disclaimer, so it never includes one, on any of the 15 questions.** That's not a probabilistic outcome that could have gone the other way by chance; it's a direct, predictable consequence of what each system prompt explicitly instructs. A larger sample size would very likely show the same near-total gap, since Variant A structurally cannot pass the "includes disclaimer" criterion under its own instructions.

**What the small sample size genuinely couldn't resolve:** whether Variant E is meaningfully *more accurate* than A, independent of the disclaimer requirement. On raw factual correctness (ignoring the disclaimer criterion entirely), both variants performed almost identically — A actually produced one clean failure Variant E didn't (Q12's broken self-correcting response), while E introduced one small fabrication A didn't (Q12's unstated "long-term care policy" caveat). Both variants have essentially equivalent underlying accuracy; the entire measured gap comes from compliance behavior, not from one variant reasoning better than the other.

## Conclusion

The experiment confirms the Day 12 hypothesis at 3x the original sample size: **Variant E should be the production system prompt**, primarily because it reliably enforces the compliance disclaimer that a real health-coverage assistant needs on every answer, not because it's a smarter or more accurate variant. The one genuinely interesting finding beyond the original hypothesis is Q12: Variant A produced an outright broken, self-contradicting response (a real reliability failure independent of the disclaimer issue), while Variant E's equivalent answer was clean but introduced a small unsupported detail — a reminder that even the "winning" variant isn't perfectly grounded, and periodic spot-checking for fabrication remains necessary regardless of which prompt variant is in production.
