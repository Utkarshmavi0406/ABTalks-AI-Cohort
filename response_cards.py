"""
response_cards.py
Day 19 — Response Formatting & Rich Outputs

Defines structured card schemas for claim status and coverage summaries,
plus helpers that try to build one from a member's question by querying
coverage.db directly (independent of the free-text SQL results already
used elsewhere, so the card data is always precisely typed).
"""

import re
import sqlite3
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "coverage.db"

# Mirrors the exclusions list used in tool_calling_chatbot.py (Day 13),
# kept in sync manually since both derive from the same synthetic benefits.txt
EXCLUDED_PROCEDURES = {
    "cosmetic surgery", "dental care (adult)", "long-term care",
    "private-duty nursing", "routine eye care (adult)", "weight loss programs",
}

KNOWN_PROCEDURES = [
    "cosmetic surgery", "dental care (adult)", "long-term care",
    "private-duty nursing", "routine eye care (adult)", "weight loss programs",
    "x-ray", "surgery",
]


class ClaimStatusCard(BaseModel):
    claim_id: str
    status: str
    amount: float
    date: str


class CoverageSummaryCard(BaseModel):
    plan_name: str
    deductible: float
    copay: float
    covered: bool


def _extract_claim_id(text: str) -> Optional[str]:
    match = re.search(r"c-?\d{3,5}", text, re.IGNORECASE)
    if not match:
        return None
    cid = match.group().upper().replace("-", "")
    return cid if cid.startswith("C") else "C" + cid


def _extract_plan_name(text: str) -> Optional[str]:
    for plan in ["gold ppo", "silver hmo", "bronze hmo", "gold", "silver", "bronze"]:
        if plan in text.lower():
            return plan
    return None


def _extract_procedure(text: str) -> Optional[str]:
    lowered = text.lower()
    for proc in KNOWN_PROCEDURES:
        if proc in lowered:
            return proc
    return None


def get_claim_status_card(claim_id: str) -> Optional[ClaimStatusCard]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT claim_id, status, claim_amount, date_filed FROM claims WHERE claim_id = ?",
        (claim_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return ClaimStatusCard(claim_id=row[0], status=row[1], amount=row[2], date=row[3])


def get_coverage_summary_card(plan_keyword: str, procedure: str) -> Optional[CoverageSummaryCard]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT plan_name, annual_deductible, copay_pct FROM plans WHERE LOWER(plan_name) LIKE ?",
        (f"%{plan_keyword}%",),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    covered = procedure.strip().lower() not in EXCLUDED_PROCEDURES
    return CoverageSummaryCard(plan_name=row[0], deductible=row[1], copay=row[2], covered=covered)


def try_build_card(question: str):
    """Inspect a question and, if it clearly maps to a claim lookup or a
    plan+procedure coverage check, return the matching card. Returns None
    if no card applies -- the caller should fall back to plain text."""
    claim_id = _extract_claim_id(question)
    if claim_id:
        return get_claim_status_card(claim_id)

    plan_keyword = _extract_plan_name(question)
    procedure = _extract_procedure(question)
    if plan_keyword and procedure:
        return get_coverage_summary_card(plan_keyword, procedure)

    return None
