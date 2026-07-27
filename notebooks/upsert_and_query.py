import json
import numpy as np
import chromadb
from pathlib import Path
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "knowledge_base.jsonl"
EMBEDDINGS_PATH = ROOT / "embeddings.npy"
CHROMA_DIR = ROOT / "chroma_data"

# ---------- Step 1: load inputs ----------
chunks = []
with open(KB_PATH, "r", encoding="utf-8") as f:
    for line in f:
        chunks.append(json.loads(line))

embeddings = np.load(EMBEDDINGS_PATH)
assert len(chunks) == embeddings.shape[0], "Mismatch: knowledge_base.jsonl rows != embeddings.npy rows"
print(f"Loaded {len(chunks)} chunks and {embeddings.shape} embeddings")

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection("coverage_kb")

# ---------- Step 2: batch-upsert in batches of 100 ----------
BATCH_SIZE = 100
for start in range(0, len(chunks), BATCH_SIZE):
    end = start + BATCH_SIZE
    batch_chunks = chunks[start:end]
    batch_embeddings = embeddings[start:end]

    collection.upsert(
        ids=[c["id"] for c in batch_chunks],
        embeddings=batch_embeddings.tolist(),
        documents=[c["text"] for c in batch_chunks],
        metadatas=[
            {
                "source_file": c["source_file"],
                "source_type": c["source_type"],
                "plan_type": c["plan_type"],
                "section": c["section"],
            }
            for c in batch_chunks
        ],
    )
    print(f"Upserted batch {start}-{end}")

# ---------- Step 3: verify count ----------
count = collection.count()
print(f"\nCollection count: {count} (expected {len(chunks)})")
assert count == len(chunks), "Collection count doesn't match chunk total!"

# ---------- Step 4: raw test query ----------
model = SentenceTransformer("all-MiniLM-L6-v2")
query_text = "Is physical therapy covered under the Silver plan?"
query_embedding = model.encode(query_text).tolist()

results = collection.query(query_embeddings=[query_embedding], n_results=5)

print("\n--- Raw query results (unfiltered) ---")
for i, (doc_id, doc, meta, dist) in enumerate(zip(
    results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
)):
    print(f"\n[{i+1}] id={doc_id} plan_type={meta['plan_type']} section={meta['section']} distance={dist:.4f}")
    print(doc[:200])

# ---------- Step 6: filtered query ----------
# Note: our actual plan_type values are "Gold PPO" / "Silver HMO" / "Bronze HMO" / "general",
# not bare "Silver" — filtering on the exact stored value
filtered_results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5,
    where={"plan_type": "Silver HMO"},
)

print("\n--- Filtered query results (plan_type=Silver HMO) ---")
for i, (doc_id, doc, meta, dist) in enumerate(zip(
    filtered_results["ids"][0], filtered_results["documents"][0],
    filtered_results["metadatas"][0], filtered_results["distances"][0]
)):
    print(f"\n[{i+1}] id={doc_id} plan_type={meta['plan_type']} section={meta['section']} distance={dist:.4f}")
    print(doc[:200])