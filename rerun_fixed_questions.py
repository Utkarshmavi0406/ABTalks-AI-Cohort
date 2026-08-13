"""
rerun_fixed_questions.py
Day 27 — re-runs just the 3 questions that failed before the Day 27 fix,
for a clean before/after comparison in ragas_scorecard.md.
"""

import json
from ragas_run import (
    score_faithfulness, score_answer_relevancy,
    score_context_precision, score_context_recall,
)
from retrieval_engine import retrieve
from rag_chatbot import generate_answer

RETEST_QUESTIONS = [
    {
        "question": "Which plan has the lowest monthly premium?",
        "ground_truth": "The Bronze HMO plan has the lowest monthly premium at $150.",
    },
    {
        "question": "Which plan has the highest monthly premium?",
        "ground_truth": "The Gold PPO plan has the highest monthly premium at $500.",
    },
    {
        "question": "How does the Gold PPO plan's copay compare to the Bronze HMO plan's copay?",
        "ground_truth": "The Gold PPO plan has a 10% copay, while the Bronze HMO plan has a 30% copay -- Gold PPO's copay is lower.",
    },
]

if __name__ == "__main__":
    results = []
    for row in RETEST_QUESTIONS:
        question = row["question"]
        ground_truth = row["ground_truth"]

        retrieval_result = retrieve(question)
        context = retrieval_result["context"]
        retrieved_chunks = [c["text"] for c in retrieval_result.get("vector_results", [])]
        # Note: these are SQL-only questions, so vector_results will still be
        # empty -- context_recall's SQL-blindness (documented in the
        # scorecard) means recall will still show 0.0 here even though the
        # SQL context is now correct and complete. faithfulness/relevancy
        # are the metrics that actually prove the fix worked.
        answer = generate_answer(question, context)

        faithfulness = score_faithfulness(answer, context)
        relevancy = score_answer_relevancy(question, answer)
        precision = score_context_precision(question, retrieved_chunks) if retrieved_chunks else 1.0
        recall = score_context_recall(ground_truth, retrieved_chunks) if retrieved_chunks else 0.0

        result = {
            "question": question, "answer": answer,
            "faithfulness": faithfulness, "answer_relevancy": relevancy,
            "context_precision": precision, "context_recall": recall,
        }
        results.append(result)
        print(f"\n{question}")
        print(f"  Answer: {answer}")
        print(f"  faithfulness={faithfulness:.2f} relevancy={relevancy:.2f} "
              f"precision={precision:.2f} recall={recall:.2f}")

    with open("ragas_rerun_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved to ragas_rerun_results.json")
