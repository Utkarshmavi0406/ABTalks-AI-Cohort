import json
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "knowledge_base.jsonl"
EMBEDDINGS_PATH = ROOT / "embeddings.npy"
PLOT_OUTPUT = ROOT / "embeddings_2d.png"

# Load chunks (for their section labels) and embeddings (index-aligned)
chunks = []
with open(KB_PATH, "r", encoding="utf-8") as f:
    for line in f:
        chunks.append(json.loads(line))

embeddings = np.load(EMBEDDINGS_PATH)
assert len(chunks) == embeddings.shape[0], "Mismatch between knowledge_base.jsonl and embeddings.npy row count!"

# Step 5: reduce 384-dim vectors down to 2D
pca = PCA(n_components=2)
coords_2d = pca.fit_transform(embeddings)

# Color-code by section
sections = [chunk["section"] for chunk in chunks]
unique_sections = sorted(set(sections))
colors = plt.cm.tab10.colors  # up to 10 distinct colors
section_to_color = {section: colors[i % len(colors)] for i, section in enumerate(unique_sections)}

plt.figure(figsize=(10, 8))
for section in unique_sections:
    idx = [i for i, s in enumerate(sections) if s == section]
    plt.scatter(
        coords_2d[idx, 0],
        coords_2d[idx, 1],
        label=section,
        color=section_to_color[section],
        alpha=0.7,
        s=60,
    )

plt.title("Knowledge Base Chunks — PCA 2D Projection (colored by section)")
plt.xlabel("PC1")
plt.ylabel("PC2")
plt.legend(title="Section")
plt.tight_layout()

plt.savefig(PLOT_OUTPUT, dpi=150)
print(f"Saved plot to {PLOT_OUTPUT}")

print(f"\nExplained variance (PC1, PC2): {pca.explained_variance_ratio_}")
print(f"Total variance captured in 2D: {sum(pca.explained_variance_ratio_):.2%}")