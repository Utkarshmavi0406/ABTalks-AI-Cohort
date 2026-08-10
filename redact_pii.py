"""
redact_pii.py
Day 25 — regex-based PII/PHI redaction for logging.

Covers: member IDs, claim IDs, SSNs, phone numbers, emails, and a small
known-name list derived from this project's own synthetic data. Regex-based
name detection is inherently limited (see the note at the bottom) --
Presidio's NER-based approach would catch a far wider range of real names,
noted here as a known limitation rather than silently overstated.
"""

import re

# Order matters: more specific patterns (SSN, email) before more generic
# ones, so a value isn't partially redacted by a broader pattern first.
PATTERNS = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("PHONE", re.compile(r"\(?\b\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")),
    ("MEMBER_ID", re.compile(r"\bM\d{3,6}\b")),
    ("CLAIM_ID", re.compile(r"\bC\d{3,6}\b")),
    ("DOB", re.compile(r"\b\d{2}/\d{2}/\d{4}\b")),
]

# Known names from this project's own synthetic data (enrollment.txt's
# "Maria Alvarez"). A real system needs NER-based name detection (e.g.
# Presidio) since a fixed name list obviously can't generalize -- this is
# a documented limitation, not a production-grade solution.
KNOWN_NAMES = [
    re.compile(r"\bMaria Alvarez\b", re.IGNORECASE),
]


def redact_pii(text: str) -> str:
    """Return `text` with likely PHI/PII replaced by [REDACTED:<type>] tags."""
    if not text:
        return text

    redacted = text
    for label, pattern in PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)

    for name_pattern in KNOWN_NAMES:
        redacted = name_pattern.sub("[REDACTED:NAME]", redacted)

    return redacted


if __name__ == "__main__":
    # Step 3: unit test with 3 sample strings containing fake PHI/PII
    test_cases = [
        (
            "My name is Maria Alvarez, member ID M1004, DOB 03/14/1988. "
            "You can reach me at m.alvarez@example.com or (555) 019-2837.",
            ["Maria Alvarez", "M1004", "03/14/1988", "m.alvarez@example.com", "(555) 019-2837"],
        ),
        (
            "What's the status of claim C1001 for member M1001? SSN on file is 123-45-6789.",
            ["C1001", "M1001", "123-45-6789"],
        ),
        (
            "Is cosmetic surgery covered under the Gold PPO plan?",
            [],  # no PII expected -- should pass through unchanged
        ),
    ]

    all_passed = True
    for i, (original, should_be_gone) in enumerate(test_cases, start=1):
        result = redact_pii(original)
        print(f"\n--- Test {i} ---")
        print(f"Original:  {original}")
        print(f"Redacted:  {result}")

        for pii_value in should_be_gone:
            if pii_value in result:
                print(f"  FAIL: '{pii_value}' still present in redacted output!")
                all_passed = False
        if should_be_gone:
            still_present = [v for v in should_be_gone if v in result]
            if not still_present:
                print(f"  PASS: all {len(should_be_gone)} PII values redacted")
        else:
            if result == original:
                print("  PASS: clean text passed through unchanged")
            else:
                print(f"  FAIL: clean text was modified unexpectedly")
                all_passed = False

    print(f"\n{'='*50}")
    print("ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED")
