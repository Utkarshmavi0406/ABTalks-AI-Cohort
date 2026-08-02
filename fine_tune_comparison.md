# Fine-Tune Comparison — Day 15

Base model (`Qwen2.5-0.5B-Instruct`) vs. LoRA fine-tuned version, evaluated on the 5 held-out questions from `fine_tune_test.jsonl` (never seen during training).

## Training summary

- 25 training examples, 3 epochs, LoRA rank 8 (`q_proj`, `v_proj`), MPS backend
- Training loss: 4.18 → ~2.7-2.9 (noisy but trending down)
- Mean token accuracy: ~0.37 → ~0.51

## Results

### Q1: "Is weight loss program coverage included?"
**Expected:** "No, weight loss programs are listed as an excluded service. This is not medical advice."

- **Base:** Hedges — says coverage "may vary," recommends checking with the insurer. Doesn't directly answer, but doesn't state something false either.
- **Fine-tuned:** "Yes, weight loss programs may be covered under some health plans..." — **directly contradicts** the training data, which explicitly states this is excluded. Shorter and more confident-sounding than the base model, but factually wrong.

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 3 | 3 | 1 | 3 |
| Fine-tuned | 4 | **1** | 1 | 3 |

### Q2: "What is the difference between HMO and PPO?"
**Expected:** Correct plain-language definitions of both acronyms and their tradeoffs.

- **Base:** Gets the PPO acronym wrong ("Pension Plan Organization"), rambling, uses markdown formatting inconsistent with the conversational style, response was cut off mid-sentence.
- **Fine-tuned:** Also gets both acronyms wrong ("Hospital-Managed Organization," "Provider-Payer Organization") — more concise, but equally incorrect on the actual definitions.

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 2 | 2 | 1 | 2 |
| Fine-tuned | 4 | **1** | 1 | 1 |

### Q3: "What's my out-of-pocket cost estimate for an X-ray on the Silver plan?"
**Expected:** $50 (based on the mock calculation methodology from training).

- **Base:** Refuses to give a number at all, says it needs more details, directs to the insurer.
- **Fine-tuned:** Gives a specific dollar figure ($10) in exactly the trained answer format (number + brief reasoning + disclaimer) — but the number itself is **wrong** (correct answer is $50).

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 3 | 2 | 1 | 3 |
| Fine-tuned | 5 | **1** | 5 | 4 |

### Q4: "Can I switch plans mid-year?"
**Expected:** Should decline — this information isn't in the knowledge base, and the correct behavior is to say so and redirect to support.

- **Base:** Confidently answers "Yes" — a fabricated policy claim with no basis in any provided data.
- **Fine-tuned:** Also confidently answers "Yes" with fabricated reasoning — same hallucination as the base model, though now with the disclaimer appended.

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 3 | 1 | 1 | 3 |
| Fine-tuned | 4 | **1** | 5 | 3 |

### Q5: "What's the claim status and procedure for C1005?"
**Expected:** "Claim C1005 is currently Pending. It's for an X-ray procedure with a claim amount of $50."

- **Base:** Badly hallucinated — interpreted "C1005" as a cancer diagnosis code and produced a multi-step cancer treatment explanation, which is inappropriate content entirely disconnected from the actual question, and arguably drifts toward the kind of medical content the system prompt explicitly said to avoid.
- **Fine-tuned:** Gets the status right ("pending") by pattern, but fabricates an unrelated "HIPAA website application" process instead of the actual procedure/amount.

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| Base | 1 | 1 | 1 | 1 |
| Fine-tuned | 3 | 2 | 1 | 2 |

## Score summary (average across all 5 questions)

| | Tone | Correctness | Disclaimer | Terminology |
|---|---|---|---|---|
| **Base** | 2.4 | 1.8 | 1.0 | 2.4 |
| **Fine-tuned** | 4.0 | **1.2** | 2.6 | 2.6 |

## Step 6: Conclusion

**Fine-tuning meaningfully improved tone consistency and disclaimer usage** — the fine-tuned model's answers are shorter, more direct, and end with the required disclaimer far more often (2.6 vs 1.0 average) than the base model, which almost never included it. This is exactly the kind of behavioral pattern fine-tuning is well-suited for: reinforcing a consistent output *style* across many examples.

**Fine-tuning did not improve — and slightly worsened — factual correctness** (1.2 vs 1.8 average). On every question requiring a specific fact the model hadn't seen during training (a plan's exact copay math, a specific claim's exact procedure/amount, the literal definition of an acronym), the fine-tuned model was just as wrong as the base model, and in several cases *more confidently* wrong, stating incorrect numbers and facts in the same fluent, well-formatted style it learned from training — which is arguably worse than the base model's more visible hedging, since a confident wrong answer is harder for a member to catch than an obviously uncertain one.

**Root cause:** 25 examples and a 500M-parameter model is nowhere near enough data or capacity to memorize an actual database of plans and claims. The model learned the *shape* of a good answer (concise, cites a specific number, ends with a disclaimer) without learning the *facts* behind any given plan or claim ID it wasn't explicitly trained on — because generalizing specific numeric facts to novel questions isn't something small-scale fine-tuning does; it's what retrieval (RAG) is actually built for.

**Would more prompt/retrieval tuning have gotten better results for less effort?** Yes, clearly, for this specific goal. Day 11's RAG pipeline — which retrieves the actual correct plan/claim data and grounds the LLM's answer in it — already produced far more accurate answers (9/10 good in the Day 11 comparison) than either model here achieved on factual questions, because RAG supplies the actual fact at query time rather than asking the model to have memorized it. Fine-tuning is the right tool specifically for *tone, disclaimer consistency, and terminology style* — which it demonstrably improved here — but it is the wrong tool for injecting new factual knowledge about specific plans or claims. The two techniques solve different problems and are complementary, not substitutes: the ideal system would use RAG for facts and a lightly fine-tuned model (or well-designed prompt) for consistent tone and compliance behavior on top of that retrieved, grounded context.
