import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "knowledge_base.jsonl"
EMBEDDINGS_OUTPUT = ROOT / "embeddings.npy"

model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str):
    """Return a numeric vector (numpy array) for the input string."""
    return model.encode(text)


if __name__ == "__main__":
    # Step 3: Load every chunk from knowledge_base.jsonl, in order
    chunks = []
    with open(KB_PATH, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))

    print(f"Loaded {len(chunks)} chunks from {KB_PATH}")

    # Step 3 + 4: embed in one batched call rather than one-by-one.
    # model.encode() accepts a list of strings natively and batches internally,
    # which is both faster and mirrors the "batch calls" guidance even though
    # we're running locally rather than against a paid API with rate limits.
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    print(f"Embeddings shape: {embeddings.shape}")  # should be (num_chunks, 384)

    # Save as a parallel array, index-aligned with knowledge_base.jsonl's line order
    np.save(EMBEDDINGS_OUTPUT, embeddings)
    print(f"Saved embeddings to {EMBEDDINGS_OUTPUT}")