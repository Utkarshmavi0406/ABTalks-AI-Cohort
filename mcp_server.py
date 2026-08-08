"""
mcp_server.py
Day 23 — Model Context Protocol (MCP)

Exposes check_coverage and get_claim_status as MCP tools, discoverable by
Claude Desktop / Cline. Run standalone with `python3 mcp_server.py` for a
quick manual check, or let the MCP host launch it as a subprocess after
registration (see mcp_test_notes.md for the registration steps and results).

Note on the SDK: the mission's instructions describe the older
`mcp.server.fastmcp.FastMCP` API. The installed `mcp` package (2.0.0)
renamed this to `mcp.server.mcpserver.MCPServer` -- same concept and
decorator-based tool registration, just a newer class name.
"""

import sqlite3
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "coverage.db"
sys.path.insert(0, str(ROOT))

from retrieval_engine import vector_lookup  # noqa: E402  (Day 10)

mcp = MCPServer(
    name="coverage-tools",
    description="Tools for checking health plan coverage and claim status.",
)


# ---------- Step 2 + 3: check_coverage tool ----------
@mcp.tool(
    name="check_coverage",
    description=(
        "Check whether a specific procedure is covered under a named health "
        "plan (e.g. 'Gold PPO', 'Silver HMO', 'Bronze HMO'). Combines "
        "semantic search over the plan's policy text with the plan's pricing "
        "data (premium, deductible, copay) from the plans database."
    ),
)
def check_coverage(plan_name: str, procedure: str) -> str:
    """
    Args:
        plan_name: The plan's name, e.g. "Gold PPO".
        procedure: The procedure to check, e.g. "cosmetic surgery".
    """
    # Vector search over policy text, filtered to this plan where possible
    results = vector_lookup(
        f"Is {procedure} covered?",
        where={"plan_type": plan_name},
        n_results=3,
    )
    policy_excerpts = "\n".join(f"- {r['text'][:300]}" for r in results) or "No matching policy text found."

    # Pull the plan's pricing info from Day 4's data
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT plan_name, monthly_premium, annual_deductible, copay_pct FROM plans WHERE LOWER(plan_name) = LOWER(?)",
        (plan_name,),
    )
    row = cur.fetchone()
    conn.close()

    plan_info = (
        f"{row[0]}: ${row[1]}/month premium, ${row[2]} deductible, {row[3]}% copay"
        if row else f"No plan found matching '{plan_name}'."
    )

    return (
        f"Plan info: {plan_info}\n\n"
        f"Relevant policy excerpts for '{procedure}':\n{policy_excerpts}"
    )


# ---------- Step 6: get_claim_status tool ----------
@mcp.tool(
    name="get_claim_status",
    description="Look up the status, procedure, and dollar amount for a specific claim ID (e.g. 'C1001').",
)
def get_claim_status(claim_id: str) -> str:
    """
    Args:
        claim_id: The claim ID to look up, e.g. "C1001".
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT claim_id, status, procedure, claim_amount, date_filed FROM claims WHERE claim_id = ?",
        (claim_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return f"No claim found with ID {claim_id}."

    return (
        f"Claim {row[0]}: status={row[1]}, procedure={row[2]}, "
        f"amount=${row[3]}, date_filed={row[4]}"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
