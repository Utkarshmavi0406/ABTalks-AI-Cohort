"""
multi_agent.py
Day 22 — Multi-Agent Orchestration

A Router classifies each question by domain (coverage / claims / enrollment)
and hands it off to a Coverage Specialist or Claims Specialist. This is a
different routing axis than Day 10's retrieve() classifier: Day 10 decides
HOW to fetch data (SQL vs vector search) for a single agent; this router
decides WHICH SPECIALIST should own the question at all, before any
retrieval mechanism is chosen.

Uses LangGraph (already installed as a langchain dependency from Day 21)
rather than CrewAI, to stay on the same free, already-verified local stack.
"""

import re
import sys
from pathlib import Path
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from retrieval_engine import retrieve  # noqa: E402
from rag_chatbot import generate_answer  # noqa: E402
from tool_calling_chatbot import get_claim_status  # noqa: E402
from langchain.agents import create_agent  # noqa: E402
from langchain_agent import check_coverage, get_plan_details  # noqa: E402  (Day 21's tool-wrapped versions, with docstrings)

llm = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    model="qwen3:8b",
    temperature=0,
)


class AgentState(TypedDict):
    question: str
    route: str
    answer: str


# ---------- Step 2: Router ----------
def router_node(state: AgentState) -> AgentState:
    prompt = (
        "Classify the following member question into exactly one domain: "
        "coverage, claims, or enrollment. "
        "Reply with only that single word, nothing else.\n\n"
        f"Question: {state['question']}"
    )
    response = llm.invoke(prompt)
    raw = response.content.strip().lower()

    if "claim" in raw:
        route = "claims"
    elif "enroll" in raw:
        route = "enrollment"
    else:
        route = "coverage"  # default/fallback domain

    print(f"[ROUTER] '{state['question']}' -> {route} (raw model output: {raw!r})")
    return {**state, "route": route}


def route_decision(state: AgentState) -> str:
    if state["route"] == "claims":
        return "claims_specialist"
    # Enrollment has no dedicated specialist today (no structured enrollment
    # data beyond the raw enrollment.txt chunk); Coverage Specialist is the
    # closest fit since it already has vector access to all raw_text sources.
    return "coverage_specialist"


# ---------- Step 3a: Coverage Specialist ----------
# Uses real tool-calling (like Day 21's single agent) rather than pure RAG,
# so it can resolve plan IDs deterministically via get_plan_details/
# check_coverage instead of relying on plan *names* appearing in retrieved
# text -- an earlier version of this specialist used retrieve()+generate_answer
# directly and failed on plan-ID questions for exactly that reason.
coverage_agent = create_agent(
    model=llm,
    tools=[check_coverage, get_plan_details],
    system_prompt=(
        "You are the Coverage Specialist. Use the available tools to look up "
        "plan details and coverage/exclusion information. If a tool doesn't "
        "have the answer, use general policy knowledge from context if given, "
        "otherwise say you don't know and suggest contacting support."
    ),
)


def coverage_specialist_node(state: AgentState) -> AgentState:
    result = coverage_agent.invoke({"messages": [("user", state["question"])]})
    final_message = result["messages"][-1]
    print(f"[COVERAGE SPECIALIST] tool calls used: "
          f"{[m.tool_calls for m in result['messages'] if getattr(m, 'tool_calls', None)]}")
    return {**state, "answer": final_message.content}


# ---------- Step 3b: Claims Specialist ----------
def claims_specialist_node(state: AgentState) -> AgentState:
    match = re.search(r"c-?\d{3,5}", state["question"], re.IGNORECASE)
    claim_id = None
    if match:
        claim_id = match.group().upper().replace("-", "")
        if not claim_id.startswith("C"):
            claim_id = "C" + claim_id

    if claim_id:
        try:
            claim_data = get_claim_status(claim_id)
            print(f"[CLAIMS SPECIALIST] looked up {claim_id}: {claim_data}")
            prompt = (
                "You are the Claims Specialist. Using ONLY this claim data, "
                f"answer the member's question in one or two sentences.\n\n"
                f"Claim data: {claim_data}\n\nQuestion: {state['question']}"
            )
            response = llm.invoke(prompt)
            answer = response.content
        except ValueError as e:
            answer = f"I couldn't find that claim: {e}. Please contact support."
    else:
        # No claim ID found in a claims-routed question -- fall back to
        # general retrieval rather than failing outright
        retrieval_result = retrieve(state["question"])
        answer = generate_answer(state["question"], retrieval_result["context"])

    return {**state, "answer": answer}


# ---------- Step 4: wire the graph ----------
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


if __name__ == "__main__":
    # Step 5: same 5 questions as Day 21, for a direct comparison
    test_questions = [
        "What are the plan details for P101?",
        "What's the status of claim C1001?",
        "Is cosmetic surgery covered under plan P101?",
        "Does plan P103 cover an X-ray?",
        "What is health insurance in general?",
    ]

    for q in test_questions:
        print(f"\n{'='*80}")
        result = app.invoke({"question": q, "route": "", "answer": ""})
        print(f"Final Answer: {result['answer']}")
