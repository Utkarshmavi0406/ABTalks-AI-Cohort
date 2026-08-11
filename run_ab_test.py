"""
run_ab_test.py
Day 26 — runs 15 test questions through Variant A and Variant E (Day 12's
prompts) and logs both answer sets side by side for scoring.
"""

from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

from retrieval_engine import retrieve

load_dotenv()

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "qwen3:8b"

VARIANT_A = """You are a health coverage information assistant. Follow these rules strictly:
1. Answer ONLY using the retrieved context provided. Do not use outside knowledge.
2. When citing a benefit, cite the exact plan name, dollar amount, or percentage as written in the context.
3. If the context does not contain the answer, respond exactly: "I don't have that information in our records. Please contact member support for details."
4. You are not a medical professional. If a question asks for medical advice, diagnosis, or treatment recommendations, refuse outright and direct the member to consult a licensed healthcare provider.
5. Do not speculate, infer, or extrapolate beyond what is explicitly stated in the context."""

VARIANT_E = """You are a health coverage assistant helping members understand their benefits clearly and kindly.

- Answer using ONLY the provided context -- never use outside knowledge or guess.
- Before answering, internally check which plan and which section (coverage/exclusions/claims/enrollment) the question relates to, and confirm the context actually covers that plan and topic.
- Cite exact numbers, percentages, and plan names as written in the context.
- If the context doesn't contain the answer, say so warmly but clearly, and point the member to support -- do not soften this into a guess.
- If asked something resembling medical advice, redirect the member to a licensed healthcare provider.
- Keep answers concise: 2-4 sentences unless more detail is genuinely needed.
- End every answer with: "This is not medical advice."."""

TEST_QUESTIONS = [
    "What's my copay on the Gold PPO plan?",
    "What's the status of claim C1001?",
    "Is cosmetic surgery excluded from coverage?",
    "How much is the deductible on the Silver HMO plan?",
    "What about the premium for Bronze HMO?",
    "Is dental care covered for adults?",
    "What's the status of claim C1003?",
    "Does the Gold PPO plan cover routine eye care?",
    "What's my out-of-pocket cost for an X-ray?",
    "Is physical therapy covered?",
    "What's the status of claim C1004?",
    "Are private-duty nursing services covered?",
    "Is weight loss coverage included?",
    "What's the status of claim C1005?",
    "Is acupuncture covered?",
]


def generate_with_variant(system_prompt: str, question: str, context: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"},
        ],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    results = []
    for q in TEST_QUESTIONS:
        context = retrieve(q)["context"]
        answer_a = generate_with_variant(VARIANT_A, q, context)
        answer_e = generate_with_variant(VARIANT_E, q, context)
        results.append({"question": q, "variant_a": answer_a, "variant_e": answer_e})

        print(f"\n{'='*80}\nQ: {q}")
        print(f"\n--- Variant A ---\n{answer_a}")
        print(f"\n--- Variant E ---\n{answer_e}")

    import json
    with open("ab_test_raw_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n\nSaved {len(results)} question results to ab_test_raw_results.json")
