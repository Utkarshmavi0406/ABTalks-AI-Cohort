"""
langchain_agent.py
Day 21 — Agentic Frameworks: LangChain Agents & Tool Use

Wraps the Day 13 coverage tools as LangChain tools and runs them through a
ReAct-style agent. Note: LangChain 1.x replaced create_react_agent/
AgentExecutor with a unified create_agent (built on LangGraph) -- it
performs the same reasoning-loop-with-tools behavior, just via native
tool-calling rather than text-parsed ReAct. Since it doesn't print classic
Thought/Action/Observation traces automatically, this script reconstructs
that format from the agent's returned message list.
"""

import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# ---------- Step 2: wrap Day 13 tools as LangChain tools ----------
# LangChain's create_agent auto-generates each tool's schema from type hints
# and uses the docstring as the description the agent reads to decide when
# to call it -- so the docstrings below are doing real work, not just
# documentation.
from tool_calling_chatbot import (  # noqa: E402
    check_coverage as _check_coverage,
    get_claim_status as _get_claim_status,
    get_plan_details as _get_plan_details,
)


def check_coverage(plan_id: str, procedure: str) -> dict:
    """Check whether a specific procedure is covered under a given health plan.
    Use this when the member asks if something is covered or excluded.
    plan_id example: 'P101'. procedure example: 'cosmetic surgery'."""
    try:
        return _check_coverage(plan_id, procedure)
    except Exception as e:
        return {"error": str(e)}


def get_claim_status(claim_id: str) -> dict:
    """Look up the status, procedure, and dollar amount for a specific
    insurance claim. Use this when the member asks about a claim, e.g.
    'What's the status of claim C1001?'. claim_id example: 'C1001'."""
    try:
        return _get_claim_status(claim_id)
    except Exception as e:
        return {"error": str(e)}


def get_plan_details(plan_id: str) -> dict:
    """Get the monthly premium, annual deductible, copay percentage, and
    network tier for a specific plan. Use this when the member asks about
    plan costs or details. plan_id example: 'P101'."""
    try:
        return _get_plan_details(plan_id)
    except Exception as e:
        return {"error": str(e)}


TOOLS = [check_coverage, get_claim_status, get_plan_details]


# ---------- Step 1 + 3: LLM + ReAct-style agent ----------
llm = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    model="qwen3:8b",
    temperature=0,
)

agent = create_agent(
    model=llm,
    tools=TOOLS,
    system_prompt=(
        "You are a health coverage assistant. Use the available tools to "
        "look up plan details, claim status, and coverage information. "
        "If a question doesn't require looking anything up, answer directly "
        "without calling a tool."
    ),
)


# ---------- Step 4: reconstruct a ReAct-style trace from the result ----------
def format_trace(question: str, result: dict) -> str:
    lines = [f"Question: {question}"]
    for msg in result["messages"]:
        msg_type = type(msg).__name__
        if msg_type == "HumanMessage":
            continue  # already printed as "Question" above
        elif msg_type == "AIMessage":
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    lines.append("Thought: I need to look this up using a tool.")
                    lines.append(f"Action: {tc['name']}")
                    lines.append(f"Action Input: {tc['args']}")
            elif msg.content:
                lines.append("Thought: I now know the final answer.")
                lines.append(f"Final Answer: {msg.content}")
        elif msg_type == "ToolMessage":
            lines.append(f"Observation: {msg.content}")
    return "\n".join(lines)


if __name__ == "__main__":
    # Step 4: 5 test questions
    test_questions = [
        "What are the plan details for P101?",             # expect: get_plan_details
        "What's the status of claim C1001?",                # expect: get_claim_status
        "Is cosmetic surgery covered under plan P101?",      # expect: check_coverage
        "Does plan P103 cover an X-ray?",                    # expect: check_coverage (2nd call)
        "What is health insurance in general?",              # expect: no tool call
    ]

    for q in test_questions:
        print(f"\n{'='*80}")
        result = agent.invoke({"messages": [("user", q)]}, {"recursion_limit": 10})
        print(format_trace(q, result))
