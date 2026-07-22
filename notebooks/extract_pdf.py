import pdfplumber
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # Daily Task root
SOURCE = ROOT / "source_docs" / "Summary_of_Benefits_and_Coverage.pdf"
OUTPUT = ROOT / "raw_text" / "benefits.txt"



text_parts = []
with pdfplumber.open(SOURCE) as pdf:
    for i, page in enumerate(pdf.pages, start=1):
        page_text = page.extract_text()
        if page_text:
            text_parts.append(f"--- Page {i} ---\n{page_text}")

full_text = "\n\n".join(text_parts)

OUTPUT.parent.mkdir(exist_ok=True)
OUTPUT.write_text(full_text, encoding="utf-8")
print(f"Wrote {len(full_text)} characters to {OUTPUT}")