"""
Day 11 — RAG End-to-End
Chains retrieve() -> generate_answer() into one full RAG pipeline,
with a grounding prompt and a streaming-mode test.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from retrieval_engine import retrieve

load_dotenv()

ROOT = Path(__file__).resolve().parent

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # Ollama ignores the key value, but the SDK requires one to be set
)

MODEL = "qwen3:8b"

GROUNDING_PROMPT = """Answer using ONLY the context below.
If the answer isn't in the context, say you don't know and suggest the member contact support.
This is not medical advice.

Context: {context}

Question: {question}"""


# ---------- Step 3: generate_answer ----------
def generate_answer(question: str, context: str) -> str:
    prompt = GROUNDING_PROMPT.format(context=context, question=question)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# ---------- Day 18: streaming generation ----------
def generate_answer_stream(question: str, context: str):
    """Yield answer tokens one at a time as they arrive from the LLM."""
    prompt = GROUNDING_PROMPT.format(context=context, question=question)
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ---------- Step 4: chain retrieve -> generate ----------
def retrieve_and_answer(question: str) -> dict:
    retrieval_result = retrieve(question)
    answer = generate_answer(question, retrieval_result["context"])
    return {
        "question": question,
        "classification": retrieval_result["classification"],
        "context": retrieval_result["context"],
        "answer": answer,
    }


# ---------- Step 7: streaming test ----------
def test_streaming(question: str, context: str):
    prompt = GROUNDING_PROMPT.format(context=context, question=question)
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    print("Streaming response:\n")
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()  # newline at the end


if __name__ == "__main__":
    # ---------- Step 5: run the 10 Day 10 test questions through the full pipeline ----------
    test_questions = [
        "What's my copay on the Gold PPO plan?",
        "Is maternity care covered on the Bronze plan?",
        "What's the status of claim C1001?",
        "What is the deductible on the Silver plan?",
        "Are cosmetic surgeries excluded from coverage?",
        "How much is the premium for the Bronze HMO plan?",
        "What's the copay for the Gold PPO plan and is physical therapy covered?",
        "Is dental care covered for adults?",
        "What's the status of claim C1003?",
        "Does the Gold PPO plan cover routine eye care?",
    ]

    for q in test_questions:
        result = retrieve_and_answer(q)
        print(f"\n{'='*80}\nQ: {q}")
        print(f"Classification: {result['classification']}")
        print(f"Answer:\n{result['answer']}")

    # ---------- Step 7: streaming test ----------
    print(f"\n{'='*80}\nSTREAMING TEST")
    sample_result = retrieve("What's my copay on the Gold PPO plan?")
    test_streaming("What's my copay on the Gold PPO plan?", sample_result["context"])