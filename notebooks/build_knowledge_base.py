import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from langchain_text_splitters import RecursiveCharacterTextSplitter

ROOT = Path(__file__).resolve().parent.parent
RAW_TEXT_DIR = ROOT / "raw_text"
DATA_DIR = ROOT / "data"
OUTPUT = ROOT / "knowledge_base.jsonl"

NOW = datetime.now(timezone.utc).isoformat()

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

records = []

# Header lines in benefits.txt that mark the start of a new section.
# Everything after a header (until the next header) is tagged with that section.
BENEFITS_HEADERS = {
    "Important Questions": "coverage",
    "Common Medical Events": "coverage",
    "Excluded Services & Other Covered Services": "exclusions",
    "Your Rights to Continue Coverage": "coverage",
}


# ---------- Step 2 + 3: load raw_text/*.txt and chunk section-aware ----------
def process_text_file(path: Path):
    filename = path.name
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    grouped = []
    if filename == "claims_process.txt":
        grouped = [("claims", "\n".join(lines))]
    elif filename == "enrollment.txt":
        grouped = [("enrollment", "\n".join(lines))]
    elif filename == "benefits.txt":
        # Header-based: current section persists until a new header line appears.
        # This keeps multi-line clauses (like the exclusions list) intact even
        # when only the first line contains an obvious trigger word.
        current_section = "coverage"
        current_blob = []
        for line in lines:
            if line in BENEFITS_HEADERS:
                if current_blob:
                    grouped.append((current_section, "\n".join(current_blob)))
                    current_blob = []
                current_section = BENEFITS_HEADERS[line]
            current_blob.append(line)
        if current_blob:
            grouped.append((current_section, "\n".join(current_blob)))
    else:
        # faq_page.txt and any other general reference content: not one of
        # our actual policy documents, so it doesn't map onto exclusions/claims/
        # enrollment — treat it uniformly as general coverage-reference content.
        grouped = [("coverage", "\n".join(lines))]

    plan_type = "Gold PPO" if filename == "benefits.txt" else "general"

    chunk_index = 0
    for section, blob in grouped:
        # Step 3: RecursiveCharacterTextSplitter, chunk_size=500, overlap=50
        chunks = splitter.split_text(blob)
        for chunk in chunks:
            records.append({
                "id": f"{filename.replace('.txt', '')}_chunk_{chunk_index}",
                "text": chunk,
                "source_file": filename,
                "source_type": "unstructured",
                "plan_type": plan_type,
                "section": section,
                "ingested_at": NOW,
            })
            chunk_index += 1


for txt_file in sorted(RAW_TEXT_DIR.glob("*.txt")):
    process_text_file(txt_file)


# ---------- Step 2: Day 4 plans -> one chunk per plan ----------
plans = pd.read_csv(DATA_DIR / "plans.csv")
for _, row in plans.iterrows():
    text = (
        f"{row['plan_name']}: ${row['monthly_premium']}/month premium, "
        f"${row['annual_deductible']} deductible, {row['copay_pct']}% copay, "
        f"network: {row['network_tier']} ({row['coverage_type']})"
    )
    records.append({
        "id": f"plan_{row['plan_id']}",
        "text": text,
        "source_file": "plans.csv",
        "source_type": "structured",
        "plan_type": row["plan_name"],
        "section": "coverage",
        "ingested_at": NOW,
    })


# ---------- Step 5: write JSONL ----------
with open(OUTPUT, "w", encoding="utf-8") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Wrote {len(records)} records to {OUTPUT}")


# ---------- Step 6: sanity check ----------
print(f"\nTotal chunk count: {len(records)}")
print("\n--- 5 random chunks ---")
for r in random.sample(records, min(5, len(records))):
    print(f"\n[{r['id']}] section={r['section']} plan_type={r['plan_type']} source_type={r['source_type']}")
    print(r["text"][:300])