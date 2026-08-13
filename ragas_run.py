"""
ragas_run.py
Day 27 — Evaluation Frameworks

Runs the eval set through the full RAG pipeline and scores each answer on
the 4 RAGAS metrics (faithfulness, answer_relevancy, context_precision,
context_recall).

Note on the library: `ragas` (both the latest release and the commonly-
recommended pinned 0.3.9 fallback) currently fails to import at all --
`ragas/llms/base.py` still imports `ChatVertexAI` from
`langchain_community.chat_models.vertexai`, a path that no longer exists
now that `langchain-community` has deprecated and removed that integration
(confirmed as a currently open, unresolved upstream bug, not specific to
this environment). Rather than risk downgrading `langchain-community` and
breaking the working chatbot (which depends on the current `langchain`/
`langgraph` stack from Days 21-24), this script implements the same 4
metrics directly as LLM-as-judge scoring functions -- the same underlying
technique RAGAS itself uses for these metrics, just without the broken
import chain.
"""

import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from retrieval_engine import retrieve  # noqa: E402
from rag_chatbot import generate_answer  # noqa: E402

load_dotenv()
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "qwen3:8b"


def llm_judge_score(prompt: str) -> float:
    """Ask the LLM to score something 0.0-1.0, robustly parse the number."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt + "\n\nRespond with ONLY a number between 0.0 and 1.0, nothing else."}],
    )
    text = response.choices[0].message.content.strip()
    match = re.search(r"(\d+\.?\d*)", text)
    if not match:
        print(f"[WARNING] Could not parse judge score from: {text!r}, defaulting to 0.5")
        return 0.5
    score = float(match.group(1))
    return max(0.0, min(1.0, score))  # clamp to [0, 1]


def score_faithfulness(answer: str, context: str) -> float:
    prompt = (
        "Given this retrieved context and this generated answer, rate how much of "
        "the answer's content is directly supported by the context. "
        "1.0 = every claim in the answer is backed by the context. "
        "0.0 = the answer is entirely unsupported or fabricated.\n\n"
        f"Context: {context}\n\nAnswer: {answer}"
    )
    return llm_judge_score(prompt)


def score_answer_relevancy(question: str, answer: str) -> float:
    prompt = (
        "Given this question and this answer, rate how relevant and on-topic "
        "the answer is. 1.0 = directly and completely addresses the question. "
        "0.0 = completely off-topic or a non-answer.\n\n"
        f"Question: {question}\n\nAnswer: {answer}"
    )
    return llm_judge_score(prompt)


def score_context_precision(question: str, retrieved_chunks: list[str]) -> float:
    chunks_text = "\n---\n".join(retrieved_chunks)
    prompt = (
        "Given this question and these retrieved context chunks, rate what "
        "fraction of the chunks are actually relevant and useful for answering "
        "the question. 1.0 = all chunks are relevant. 0.0 = none are relevant.\n\n"
        f"Question: {question}\n\nRetrieved chunks:\n{chunks_text}"
    )
    return llm_judge_score(prompt)


def score_context_recall(ground_truth: str, retrieved_chunks: list[str]) -> float:
    chunks_text = "\n---\n".join(retrieved_chunks)
    prompt = (
        "Given this ideal/ground-truth answer and these retrieved context chunks, "
        "rate how much of the information needed to produce the ground-truth answer "
        "is actually present in the retrieved chunks. 1.0 = everything needed is "
        "present. 0.0 = none of it is present.\n\n"
        f"Ground-truth answer: {ground_truth}\n\nRetrieved chunks:\n{chunks_text}"
    )
    return llm_judge_score(prompt)


def load_eval_set(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def run_evaluation(eval_set_path: str, output_path: str):
    eval_set = load_eval_set(eval_set_path)
    print(f"Loaded {len(eval_set)} eval pairs")

    results = []
    for i, row in enumerate(eval_set, start=1):
        question = row["question"]
        ground_truth = row["ground_truth"]

        # ---------- Step 3: run through the full RAG pipeline ----------
        retrieval_result = retrieve(question)
        context = retrieval_result["context"]
        retrieved_chunks = [c["text"] for c in retrieval_result.get("vector_results", [])]
        answer = generate_answer(question, context)

        # ---------- Step 4: score the 4 RAGAS metrics ----------
        faithfulness = score_faithfulness(answer, context)
        relevancy = score_answer_relevancy(question, answer)
        precision = score_context_precision(question, retrieved_chunks) if retrieved_chunks else 1.0
        recall = score_context_recall(ground_truth, retrieved_chunks) if retrieved_chunks else 0.0

        result = {
            "question": question,
            "ground_truth": ground_truth,
            "answer": answer,
            "retrieved_chunks": retrieved_chunks,
            "faithfulness": faithfulness,
            "answer_relevancy": relevancy,
            "context_precision": precision,
            "context_recall": recall,
        }
        results.append(result)

        print(f"\n[{i}/{len(eval_set)}] {question}")
        print(f"  faithfulness={faithfulness:.2f} relevancy={relevancy:.2f} "
              f"precision={precision:.2f} recall={recall:.2f}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Print summary averages
    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    print(f"\n{'='*60}\nSUMMARY (averages across {len(results)} questions)")
    for m in metrics:
        avg = sum(r[m] for r in results) / len(results)
        print(f"  {m}: {avg:.3f}")

    print(f"\nSaved full results to {output_path}")
    return results


if __name__ == "__main__":
    run_evaluation("ragas_eval_set.jsonl", "ragas_results.json")
