import chromadb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = ROOT / "chroma_data"  # local on-disk storage, persists across runs

client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# create_collection errors if it already exists, so use get_or_create
# to make this script safely re-runnable
collection = client.get_or_create_collection("coverage_kb")

print(f"Collection name: {collection.name}")
print(f"Collection count: {collection.count()}")  # should be 0, we haven't added anything yet

# Confirm it's listed among the client's collections
all_collections = client.list_collections()
print(f"\nAll collections in this Chroma instance: {[c.name for c in all_collections]}")