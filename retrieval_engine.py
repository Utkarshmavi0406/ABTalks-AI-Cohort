"""
Day 10 — Retrieval / Matching Engine
Routes a member question to SQL (structured plan/claim data), the vector DB
(policy/coverage text), or both, then merges the results into one context block.
"""

import re
import sqlite3
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "coverage.db"
CHROMA_DIR = ROOT / "chroma_data"

_model = SentenceTransformer("all-MiniLM-L6-v2")
_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_or_create_collection("coverage_kb")


# ---------- Step 1: question classifier ----------
def classify_question(question: str) -> str:
    """Label a question as 'structured', 'unstructured', or 'both'."""
    q = question.lower()

    structured_signals = [
        "deductible", "premium", "copay", "coinsurance", "cost", "price",
        "claim status", "status of claim", r"c-?\d{3,5}",
        "member id", "how much",
    ]
    unstructured_signals = [
        "covered", "coverage", "exclude", "excluded", "does not cover",
        "is it covered", "policy", "benefit", "eligible for",
    ]

    has_structured = any(re.search(sig, q) for sig in structured_signals)
    has_unstructured = any(re.search(sig, q) for sig in unstructured_signals)

    if has_structured and has_unstructured:
        return "both"
    elif has_structured:
        return "structured"
    elif has_unstructured:
        return "unstructured"
    else:
        # Ambiguous / no clear signal: default to unstructured, since policy
        # text is a reasonable fallback for open-ended member questions
        return "unstructured"


def _extract_claim_id(question: str):
    match = re.search(r"c-?\d{3,5}", question, re.IGNORECASE)
    if not match:
        return None
    cid = match.group().upper().replace("-", "")
    if not cid.startswith("C"):
        cid = "C" + cid
    return cid


def _extract_plan_name(question: str):
    for plan in ["gold ppo", "silver hmo", "bronze hmo", "gold", "silver", "bronze"]:
        if plan in question.lower():
            return plan
    return None


# ---------- Day 27: extract EVERY plan name mentioned, not just the first ----------
def _extract_all_plan_names(question: str) -> list[str]:
    """Return every plan name mentioned in the question -- needed so a
    two-plan comparison question doesn't silently drop the second plan."""
    found = []
    for plan in ["gold ppo", "silver hmo", "bronze hmo"]:
        if plan in question.lower():
            found.append(plan)
    return found


# ---------- Step 2: SQL lookup ----------
def sql_lookup(question: str) -> list[str]:
    """Convert a structured question into SQL against plans/claims, return result strings."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    results = []

    claim_id = _extract_claim_id(question)
    if claim_id:
        cur.execute(
            "SELECT claim_id, status, procedure, claim_amount FROM claims WHERE claim_id = ?",
            (claim_id,),
        )
        for row in cur.fetchall():
            results.append(f"Claim {row[0]}: status={row[1]}, procedure={row[2]}, amount=${row[3]}")

    pricing_question = any(w in question.lower() for w in ["deductible", "premium", "copay"])
    if pricing_question:
        # Day 27 fix: the old version only looked up ONE plan (the first
        # name matched) and returned nothing at all if no plan was named --
        # which silently broke cross-plan comparison questions like "which
        # plan has the lowest premium?" (found via RAGAS-style evaluation:
        # faithfulness/relevancy both scored 0.0 on exactly these questions,
        # because sql_lookup returned an empty list and the model correctly
        # had nothing to answer from).
        plan_keywords = _extract_all_plan_names(question)

        if plan_keywords:
            # One or more specific plans named -- return pricing for each
            for plan_keyword in plan_keywords:
                cur.execute(
                    "SELECT plan_name, monthly_premium, annual_deductible, copay_pct FROM plans WHERE LOWER(plan_name) LIKE ?",
                    (f"%{plan_keyword}%",),
                )
                for row in cur.fetchall():
                    results.append(f"{row[0]}: premium=${row[1]}/mo, deductible=${row[2]}, copay={row[3]}%")
        else:
            # Pricing question naming no specific plan -- this is a
            # cross-plan comparison ("which plan has the lowest premium?"),
            # so return every plan's pricing and let the LLM compare them.
            cur.execute(
                "SELECT plan_name, monthly_premium, annual_deductible, copay_pct FROM plans"
            )
            for row in cur.fetchall():
                results.append(f"{row[0]}: premium=${row[1]}/mo, deductible=${row[2]}, copay={row[3]}%")

    conn.close()
    return results


# ---------- Step 3: vector lookup ----------
def vector_lookup(question: str, where: dict | None = None, n_results: int = 5) -> list[dict]:
    """Embed the question and return the top-N relevant policy chunks."""
    query_embedding = _model.encode(question).tolist()
    kwargs = {"query_embeddings": [query_embedding], "n_results": n_results}
    if where:
        kwargs["where"] = where
    results = _collection.query(**kwargs)

    chunks = []
    for doc_id, doc, meta, dist in zip(
        results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        chunks.append({"id": doc_id, "text": doc, "metadata": meta, "distance": dist})
    return chunks


# ---------- Step 4: route + merge ----------
def retrieve(question: str) -> dict:
    """Route to sql_lookup, vector_lookup, or both; merge and de-duplicate context."""
    classification = classify_question(question)

    sql_results = []
    vector_results = []

    if classification in ("structured", "both"):
        sql_results = sql_lookup(question)

    if classification in ("unstructured", "both"):
        vector_results = vector_lookup(question)

    # Merge into one context block, de-duplicating on text content
    seen_texts = set()
    context_lines = []

    for r in sql_results:
        if r not in seen_texts:
            context_lines.append(f"[SQL] {r}")
            seen_texts.add(r)

    for chunk in vector_results:
        text = chunk["text"].strip()
        if text not in seen_texts:
            context_lines.append(f"[VECTOR:{chunk['metadata']['section']}] {text[:300]}")
            seen_texts.add(text)

    return {
        "question": question,
        "classification": classification,
        "sql_results": sql_results,
        "vector_results": vector_results,
        "context": "\n\n".join(context_lines),
    }


if __name__ == "__main__":
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
        "Which plan has the lowest monthly premium?",
        "Which plan has the highest monthly premium?",
        "How does the Gold PPO plan's copay compare to the Bronze HMO plan's copay?",
    ]

    for q in test_questions:
        result = retrieve(q)
        print(f"\n{'='*80}\nQ: {q}")
        print(f"Classification: {result['classification']}")
        print(f"Context:\n{result['context']}")
