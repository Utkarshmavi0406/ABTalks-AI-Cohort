"""
Day 13 — Advanced Prompting: Function Calling & Structured Outputs
Defines coverage tool schemas, lets the LLM decide when to call them,
executes against Day 4's coverage.db, and validates every tool result
with Pydantic before feeding it back to the model.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "coverage.db"

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "qwen3:8b"

# Day 12's winning system prompt (Variant E — hybrid)
SYSTEM_PROMPT = """You are a health coverage assistant helping members understand their benefits clearly and kindly.

- Answer using ONLY the provided context or tool results — never use outside knowledge or guess.
- Before answering, internally check which plan and which section the question relates to, and confirm the information actually covers that plan and topic.
- Cite exact numbers, percentages, and plan names as written in the tool result.
- If a tool result doesn't contain the answer, say so warmly but clearly, and point the member to support — do not soften this into a guess.
- If asked something resembling medical advice, redirect the member to a licensed healthcare provider.
- Keep answers concise: 2-4 sentences unless more detail is genuinely needed.
- End every answer with: "This is not medical advice."
"""

# Mock exclusions list, matching benefits.txt (Day 5). In a real system this
# would be a proper per-plan coverage table; hardcoded here per Day 13's
# "mock data is fine" allowance.
EXCLUDED_PROCEDURES = {
    "cosmetic surgery", "dental care (adult)", "long-term care",
    "private-duty nursing", "routine eye care (adult)", "weight loss programs",
}

# Mock base costs per procedure, used only for the out-of-pocket estimate tool
BASE_PROCEDURE_COST = {
    "x-ray": 250,
    "surgery": 1200,
}


# ---------- Step 4: Pydantic models for each tool's output ----------
class CoverageCheckResult(BaseModel):
    plan_id: str
    procedure: str
    covered: bool
    notes: str


class ClaimStatusResult(BaseModel):
    claim_id: str
    status: str
    procedure: str
    claim_amount: float


class PlanDetailsResult(BaseModel):
    plan_id: str
    plan_name: str
    monthly_premium: float
    annual_deductible: float
    copay_pct: float
    network_tier: str


class OutOfPocketEstimate(BaseModel):
    procedure: str
    plan_id: str
    estimated_cost: float
    notes: str


# ---------- Step 1: tool implementations (query Day 4's coverage.db) ----------
def check_coverage(plan_id: str, procedure: str) -> dict:
    is_excluded = procedure.strip().lower() in EXCLUDED_PROCEDURES
    result = CoverageCheckResult(
        plan_id=plan_id,
        procedure=procedure,
        covered=not is_excluded,
        notes="Excluded service per plan exclusions list." if is_excluded
              else "Not on the excluded services list (mock check; confirm with full policy for edge cases).",
    )
    return result.model_dump()


def get_claim_status(claim_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT claim_id, status, procedure, claim_amount FROM claims WHERE claim_id = ?",
        (claim_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"No claim found with id {claim_id}")

    result = ClaimStatusResult(
        claim_id=row[0], status=row[1], procedure=row[2], claim_amount=row[3]
    )
    return result.model_dump()


def get_plan_details(plan_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT plan_id, plan_name, monthly_premium, annual_deductible, copay_pct, network_tier FROM plans WHERE plan_id = ?",
        (plan_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"No plan found with id {plan_id}")

    result = PlanDetailsResult(
        plan_id=row[0], plan_name=row[1], monthly_premium=row[2],
        annual_deductible=row[3], copay_pct=row[4], network_tier=row[5],
    )
    return result.model_dump()


def estimate_out_of_pocket_cost(procedure: str, plan_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT copay_pct FROM plans WHERE plan_id = ?", (plan_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"No plan found with id {plan_id}")

    copay_pct = row[0]
    base_cost = BASE_PROCEDURE_COST.get(procedure.strip().lower())

    if base_cost is None:
        result = OutOfPocketEstimate(
            procedure=procedure, plan_id=plan_id, estimated_cost=0,
            notes="No cost data available for this procedure (mock dataset limitation).",
        )
    else:
        estimated = round(base_cost * (copay_pct / 100), 2)
        result = OutOfPocketEstimate(
            procedure=procedure, plan_id=plan_id, estimated_cost=estimated,
            notes=f"Estimated as {copay_pct}% of a ${base_cost} mock base cost for {procedure}.",
        )
    return result.model_dump()


TOOL_FUNCTIONS = {
    "check_coverage": check_coverage,
    "get_claim_status": get_claim_status,
    "get_plan_details": get_plan_details,
    "estimate_out_of_pocket_cost": estimate_out_of_pocket_cost,
}


# ---------- Step 2: tool schemas for the LLM ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_coverage",
            "description": "Check whether a specific procedure is covered under a given plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string", "description": "Plan ID, e.g. P101"},
                    "procedure": {"type": "string", "description": "Procedure name, e.g. 'cosmetic surgery'"},
                },
                "required": ["plan_id", "procedure"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_claim_status",
            "description": "Look up the status, procedure, and amount for a specific claim.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "description": "Claim ID, e.g. C1001"},
                },
                "required": ["claim_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plan_details",
            "description": "Get premium, deductible, copay, and network tier for a specific plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string", "description": "Plan ID, e.g. P101"},
                },
                "required": ["plan_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_out_of_pocket_cost",
            "description": "Estimate a member's out-of-pocket cost for a procedure under a given plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "procedure": {"type": "string", "description": "Procedure name, e.g. 'Surgery'"},
                    "plan_id": {"type": "string", "description": "Plan ID, e.g. P101"},
                },
                "required": ["procedure", "plan_id"],
            },
        },
    },
]


# ---------- Step 3: tool-execution loop ----------
def tool_calling_chat(question: str, log: list) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
    )
    message = response.choices[0].message

    if not message.tool_calls:
        # No tool call: model answered directly (Step 5's "no tool" case)
        log.append({"question": question, "tool": None, "arguments": None, "result": None})
        return message.content

    messages.append(message)

    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            arguments = {}

        try:
            func = TOOL_FUNCTIONS.get(tool_name)
            if func is None:
                raise ValueError(f"Unknown tool: {tool_name}")
            result = func(**arguments)
        except (ValidationError, ValueError, TypeError) as e:
            result = {"error": str(e)}

        log.append({
            "question": question,
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
        })

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result),
        })

    # Feed tool result back, get the final natural-language answer
    final_response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    return final_response.choices[0].message.content


if __name__ == "__main__":
    # Step 5: 5 questions each triggering a different tool, + 1 that triggers none
    test_questions = [
        "What are the plan details for P101?",              # get_plan_details
        "What's the status of claim C1001?",                # get_claim_status
        "Is cosmetic surgery covered under plan P101?",      # check_coverage
        "Estimate my out-of-pocket cost for a Surgery on plan P102.",  # estimate_out_of_pocket_cost
        "Does plan P103 cover an X-ray?",                    # check_coverage (2nd, different plan)
        "What is health insurance in general?",              # no tool expected
    ]

    call_log = []

    for q in test_questions:
        print(f"\n{'='*80}\nQ: {q}")
        answer = tool_calling_chat(q, call_log)
        print(f"Answer:\n{answer}")

    # Save the raw log for tool_call_log.md generation
    with open(ROOT / "tool_call_log_raw.json", "w") as f:
        json.dump(call_log, f, indent=2, default=str)
    print(f"\n\nLogged {len(call_log)} interactions to tool_call_log_raw.json")
