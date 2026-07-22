from pdf2image import convert_from_path
import pytesseract
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # Daily Task root
SOURCE = ROOT / "source_docs" / "enrollment_form_scanned.pdf"
OUTPUT = ROOT / "raw_text" / "enrollment.txt"

images = convert_from_path(SOURCE)

text_parts = []
for i, image in enumerate(images, start=1):
    page_text = pytesseract.image_to_string(image)
    text_parts.append(f"--- Page {i} (OCR) ---\n{page_text}")

full_text = "\n\n".join(text_parts)

OUTPUT.parent.mkdir(exist_ok=True)
OUTPUT.write_text(full_text, encoding="utf-8")
print(f"Wrote {len(full_text)} characters to {OUTPUT}")