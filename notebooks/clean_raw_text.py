import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_TEXT_DIR = ROOT / "raw_text"

def clean_text(text: str) -> str:
    # Normalize unicode (fixes many "smart quote"/mojibake-style encoding issues)
    text = unicodedata.normalize("NFKC", text)

    # Collapse multiple spaces/tabs within a line
    text = re.sub(r"[ \t]+", " ", text)

    # Strip trailing whitespace on each line
    lines = [line.rstrip() for line in text.split("\n")]

    # Collapse 3+ blank lines down to a single blank line
    cleaned_lines = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 1:
                cleaned_lines.append(line)
        else:
            blank_count = 0
            cleaned_lines.append(line.strip())

    return "\n".join(cleaned_lines).strip() + "\n"


for txt_file in RAW_TEXT_DIR.glob("*.txt"):
    original = txt_file.read_text(encoding="utf-8", errors="replace")
    cleaned = clean_text(original)
    txt_file.write_text(cleaned, encoding="utf-8")
    print(f"Cleaned {txt_file.name}: {len(original)} -> {len(cleaned)} characters")