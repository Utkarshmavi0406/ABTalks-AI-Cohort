from docx import Document
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # Daily Task root
SOURCE = ROOT / "source_docs" / "Claims_Process_Guide.docx"
OUTPUT = ROOT / "raw_text" / "claims_process.txt"

doc = Document(SOURCE)

paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
full_text = "\n".join(paragraphs)

OUTPUT.parent.mkdir(exist_ok=True)
OUTPUT.write_text(full_text, encoding="utf-8")
print(f"Wrote {len(full_text)} characters to {OUTPUT}")