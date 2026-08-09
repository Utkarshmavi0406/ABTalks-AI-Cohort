"""
multi_agent.py
Day 24 — Agentic Chatbot: Full Integration

Brings together:
- Day 22's Router + Coverage/Claims Specialist workflow
- Day 23's MCP server, called via the REAL MCP protocol (not direct
  Python function imports)
- Day 20's conversation memory (SQLite conversations table + remembered plan)
- Resilience: every tool call wrapped in a timeout, one retry, and a
  canned fallback -- never a raw crash or 500 to the member

Note: connecting to the MCP server is comparatively slow (it loads the
embedding model on startup, same as every other script this project), so
this script opens ONE persistent MCP client session at startup and reuses
it for every tool call, rather than reconnecting per call.
"""

import asyncio
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "coverage.db"
MCP_SERVER_PATH = ROOT / "mcp_server.py"
sys.path.insert(0, str(ROOT))

llm = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    model="qwen3:8b",
    temperature=0,
)

TOOL_TIMEOUT_SECONDS = 10
MAX_RETRIES = 1
FALLBACK_MESSAGE = "I'm having trouble accessing that right now, please contact member support."


# ---------- Step 2: Day 20 memory (reimplemented lightly here to avoid
# importing across the hyphenated coverage-chatbot-api/ folder name) ----------
def load_history(session_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY timestamp ASC",
        (session_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]


def save_turn(session_id: str, role: str, content: str):
    from datetime import datetime, timezone
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, role, content, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def extract_mentioned_plan(history: list[dict]) -> Optional[str]:
    plan_display_names = {"gold ppo": "Gold PPO", "silver hmo": "Silver HMO", "bronze hmo": "Bronze HMO"}
    for turn in reversed(history):
        if turn["role"] != "user":
            continue
        match = re.search(r"(gold ppo|silver hmo|bronze hmo)", turn["content"], re.IGNORECASE)
        if match:
            return plan_display_names[match.group(1).lower()]
    return None


# ---------- Step 1: real MCP client, connected once and reused ----------
class MCPToolClient:
    def __init__(self):
        self._session: Optional[ClientSession] = None
        self._streams_ctx = None
        self._session_ctx = None

    async def connect(self):
        server_params = StdioServerParameters(
            command=sys.executable,  # the currently-running Python (this venv)
            args=[str(MCP_SERVER_PATH)],
        )
        self._streams_ctx = stdio_client(server_params)
        read_stream, write_stream = await self._streams_ctx.__aenter__()
        self._session_ctx = ClientSession(read_stream, write_stream)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()

    async def close(self):
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._streams_ctx:
            await self._streams_ctx.__aexit__(None, None, None)

    # ---------- Step 3 + 4: timeout, retry, canned fallback ----------
    async def call_tool_resilient(self, tool_name: str, arguments: dict) -> str:
        attempt = 0
        last_error = None

        while attempt <= MAX_RETRIES:
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(tool_name, arguments),
                    timeout=TOOL_TIMEOUT_SECONDS,
                )
                # MCP signals a tool-side failure (e.g. unknown tool name,
                # or an exception inside the tool) via result.is_error=True,
                # NOT by raising a Python exception here -- so that has to be
                # checked explicitly, or a failed call gets silently treated
                # as a success and its error text gets passed to the LLM as
                # if it were real data.
                if getattr(result, "is_error", False):
                    raise RuntimeError(f"Tool returned an error result: {result.content}")

                if result.content and hasattr(result.content[0], "text"):
                    return result.content[0].text
                return str(result.content)
            except Exception as e:
                last_error = e
                attempt += 1
                print(f"[MCP TOOL] {tool_name} attempt {attempt} failed: {e}")

        print(f"[MCP TOOL] {tool_name} exhausted retries, falling back. Last error: {last_error}")
        return FALLBACK_MESSAGE


mcp_client = MCPToolClient()


# ---------- Graph state ----------
class AgentState(TypedDict):
    question: str
    session_id: str
    route: str
    answer: str


# ---------- Router ----------
async def router_node(state: AgentState) -> AgentState:
    prompt = (
        "Classify the following member question into exactly one domain: "
        "coverage, claims, or enrollment. Reply with only that single word.\n\n"
        f"Question: {state['question']}"
    )
    response = await llm.ainvoke(prompt)
    raw = response.content.strip().lower()
    route = "claims" if "claim" in raw else ("enrollment" if "enroll" in raw else "coverage")
    print(f"[ROUTER] '{state['question']}' -> {route}")
    return {**state, "route": route}


def route_decision(state: AgentState) -> str:
    return "claims_specialist" if state["route"] == "claims" else "coverage_specialist"


# ---------- Coverage Specialist (now calling real MCP tools) ----------
async def coverage_specialist_node(state: AgentState) -> AgentState:
    # Step 2: pull remembered plan from conversation history
    history = load_history(state["session_id"])
    mentioned_plan = extract_mentioned_plan(history)

    plan_match = re.search(r"(gold ppo|silver hmo|bronze hmo)", state["question"], re.IGNORECASE)
    plan_name = plan_match.group(1).title() if plan_match else mentioned_plan

    procedure_match = re.search(
        r"(cosmetic surgery|dental care|long-term care|private-duty nursing|routine eye care|weight loss|x-ray|surgery)",
        state["question"], re.IGNORECASE,
    )
    procedure = procedure_match.group(1) if procedure_match else None

    if plan_name and procedure:
        tool_result = await mcp_client.call_tool_resilient(
            "check_coverage", {"plan_name": plan_name, "procedure": procedure}
        )
    elif plan_name:
        tool_result = await mcp_client.call_tool_resilient(
            "check_coverage", {"plan_name": plan_name, "procedure": "general plan details"}
        )
    else:
        tool_result = "No specific plan identified in this question or conversation history."

    prompt = (
        f"You are the Coverage Specialist. Using this tool result, answer the "
        f"member's question in 2-3 sentences.\n\nTool result: {tool_result}\n\n"
        f"Question: {state['question']}"
    )
    response = await llm.ainvoke(prompt)
    return {**state, "answer": response.content}


# ---------- Claims Specialist (now calling real MCP tools) ----------
async def claims_specialist_node(state: AgentState) -> AgentState:
    match = re.search(r"c-?\d{3,5}", state["question"], re.IGNORECASE)
    if not match:
        return {**state, "answer": "I couldn't find a claim ID in your question. Please provide one, e.g. C1001."}

    claim_id = match.group().upper().replace("-", "")
    if not claim_id.startswith("C"):
        claim_id = "C" + claim_id

    tool_result = await mcp_client.call_tool_resilient("get_claim_status", {"claim_id": claim_id})

    if tool_result == FALLBACK_MESSAGE:
        return {**state, "answer": tool_result}

    prompt = (
        f"You are the Claims Specialist. Using ONLY this claim data, answer the "
        f"member's question in one or two sentences.\n\nClaim data: {tool_result}\n\n"
        f"Question: {state['question']}"
    )
    response = await llm.ainvoke(prompt)
    return {**state, "answer": response.content}


# ---------- wire the graph ----------
graph = StateGraph(AgentState)
graph.add_node("router", router_node)
graph.add_node("coverage_specialist", coverage_specialist_node)
graph.add_node("claims_specialist", claims_specialist_node)
graph.set_entry_point("router")
graph.add_conditional_edges("router", route_decision, {
    "coverage_specialist": "coverage_specialist",
    "claims_specialist": "claims_specialist",
})
graph.add_edge("coverage_specialist", END)
graph.add_edge("claims_specialist", END)
app = graph.compile()


async def run_question(question: str, session_id: str) -> str:
    save_turn(session_id, "user", question)
    result = await app.ainvoke({"question": question, "session_id": session_id, "route": "", "answer": ""})
    save_turn(session_id, "assistant", result["answer"])
    return result["answer"]


async def main():
    await mcp_client.connect()
    print("[MCP] Connected to mcp_server.py\n")

    session_id = "day24-test-session"
    test_questions = [
        "What are the plan details for the Gold PPO plan?",
        "What's the status of claim C1001?",
        "Is cosmetic surgery covered under plan P101?",
        "Does plan P103 cover an X-ray?",
        "What is health insurance in general?",
    ]

    try:
        for q in test_questions:
            print(f"\n{'='*80}")
            answer = await run_question(q, session_id)
            print(f"Final Answer: {answer}")
    finally:
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
