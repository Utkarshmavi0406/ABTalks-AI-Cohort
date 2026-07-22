import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
URL = "https://www.healthinsurance.org/faqs/what-does-medicaid-cover/"
OUTPUT = ROOT / "raw_text" / "faq_page.txt"

headers = {"User-Agent": "Mozilla/5.0 (Day5 coursework scraper)"}
resp = requests.get(URL, headers=headers, timeout=15)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")

# Strip elements that are never part of the article body
for tag in soup(["nav", "footer", "header", "script", "style", "aside", "form", "svg"]):
    tag.decompose()

# WordPress/Elementor sites (like this one) usually wrap the article in one
# of these containers. Try the likely candidates first.
content = None
for selector in ["article", ".entry-content", ".elementor-widget-theme-post-content", "main"]:
    content = soup.select_one(selector)
    if content:
        break

if content is None:
    # Fallback: just grab every <p> on the page
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
else:
    paragraphs = [p.get_text(" ", strip=True) for p in content.find_all(["p", "h2", "h3", "li"])]


# Drop the breadcrumb trail (e.g. "Home > FAQs > ...")
paragraphs = [p for p in paragraphs if not p.startswith("Home >")]

# Strip trailing footnote reference numbers (e.g. "...Medicaid. 36" -> "...Medicaid.")
def strip_footnote_markers(text):
    # Footnote right after a sentence-ending period: ". 36" -> "."
    text = re.sub(r"\.\s\d{1,3}(?=\s|$)", ".", text)
    # Footnote right before an en-dash: "35 – " -> " – " (removes the citation number, keeps the dash)
    text = re.sub(r"\s\d{1,3}(?=\s[-–—])", "", text)
    # Footnote as the very last token in a paragraph, with no trailing punctuation
    text = re.sub(r"\s\d{1,3}$", "", text)
    return text


paragraphs = [strip_footnote_markers(p) for p in paragraphs]

paragraphs = [p for p in paragraphs if p]  # drop empties
full_text = "\n\n".join(paragraphs)

OUTPUT.parent.mkdir(exist_ok=True)
OUTPUT.write_text(full_text, encoding="utf-8")
print(f"Wrote {len(full_text)} characters to {OUTPUT}")
print("\n--- preview ---\n")
print(full_text[:500])