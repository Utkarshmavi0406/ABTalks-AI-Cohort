"""
app.py
Day 18 — Full-Stack Integration & Streaming Responses
Streamlit chat UI that consumes the /chat SSE stream token-by-token.
"""

import uuid
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from response_cards import try_build_card

ROOT = Path(__file__).resolve().parent
API_URL = "http://localhost:8000"

st.set_page_config(page_title="Coverage Assistant", page_icon="⚕", layout="centered")

# ---------- Design system ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --teal-300: #7FC4BB;
    --teal-500: #57A79E;
    --teal-700: #3D8A82;
    --bg: #0E1614;
    --sidebar-bg: #12201C;
    --card: #16211E;
    --border: #253531;
    --text: #EAF2EF;
    --muted: #93A9A3;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    font-family: 'Inter', sans-serif;
    color: var(--text);
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stChatInput"] {
    background: var(--bg) !important;
}
[data-testid="stBottom"] > div {
    background: var(--bg) !important;
    border-top: 1px solid var(--border);
}

[data-testid="stSidebar"] {
    background: var(--sidebar-bg);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] label {
    font-family: 'Inter', sans-serif;
    color: var(--text);
    font-weight: 600;
}

.app-header {
    padding: 0.5rem 0 1.25rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.app-header h1 {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 2.4rem;
    color: var(--teal-300);
    margin: 0;
    letter-spacing: -0.01em;
}
.app-header p {
    font-family: 'Inter', sans-serif;
    color: var(--muted);
    margin: 0.35rem 0 0 0;
    font-size: 0.95rem;
}
.accent-rule {
    height: 3px;
    width: 64px;
    background: linear-gradient(90deg, var(--teal-700), var(--teal-300));
    border-radius: 2px;
    margin-top: 0.6rem;
}

[data-testid="stChatMessage"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.6rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] span,
[data-testid="stChatMessage"] div {
    color: var(--text) !important;
}

[data-testid="stChatInput"] {
    max-width: 760px;
    margin: 0 auto;
}
[data-testid="stChatInput"] > div {
    background: var(--card) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
[data-testid="stChatInput"] textarea {
    background: var(--card) !important;
    color: var(--text) !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    font-family: 'Inter', sans-serif;
    font-size: 1.02rem;
    padding: 0.85rem 1rem !important;
    height: 3.2rem !important;
    max-height: 8rem !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: var(--muted) !important;
    opacity: 1;
}
[data-testid="stChatInput"]:focus-within > div {
    border-color: var(--teal-500) !important;
    box-shadow: 0 0 0 2px rgba(87, 167, 158, 0.3) !important;
}

.stButton button {
    background: var(--card);
    color: var(--teal-300);
    border: 1px solid var(--teal-500);
    border-radius: 10px;
    font-weight: 500;
    transition: background 0.15s ease;
}
.stButton button:hover {
    background: var(--sidebar-bg);
    border-color: var(--teal-300);
    color: var(--teal-300);
}

.session-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: var(--muted);
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.2rem 0.5rem;
    display: inline-block;
    margin-top: 0.5rem;
}

[data-testid="stSelectbox"] > div > div {
    border-radius: 10px !important;
    border-color: var(--border) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
    <div style="display:flex; align-items:center; gap:0.9rem;">
        <svg width="44" height="44" viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M22 3 L38 9 V21 C38 31 31 38 22 41 C13 38 6 31 6 21 V9 Z"
                  fill="#16302B" stroke="#57A79E" stroke-width="2"/>
            <path d="M22 14 V28 M15 21 H29" stroke="#7FC4BB" stroke-width="3" stroke-linecap="round"/>
        </svg>
        <h1 style="margin:0;">Coverage Assistant</h1>
    </div>
    <p>Ask about your deductible, claims, or what's covered under your plan.</p>
    <div class="accent-rule"></div>
</div>
""", unsafe_allow_html=True)

ASSISTANT_AVATAR = "🩺"
USER_AVATAR = "🙂"

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "member_id" not in st.session_state:
    st.session_state.member_id = "M1001"


with st.sidebar:
    st.header("Options")

    plans_path = ROOT / "data" / "plans.csv"
    if plans_path.exists():
        plans_df = pd.read_csv(plans_path)
        plan_names = plans_df["plan_name"].tolist()
        selected_plan = st.selectbox("Your plan", options=plan_names)
    else:
        st.warning("data/plans.csv not found — plan selector unavailable.")
        selected_plan = None

    st.markdown("<div style='margin: 1rem 0; border-top: 1px solid var(--border);'></div>", unsafe_allow_html=True)

    if st.button("New conversation", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.markdown(
        f"<div class='session-badge'>session: {st.session_state.session_id[:8]}...</div>",
        unsafe_allow_html=True,
    )


if not st.session_state.messages:
    st.markdown(
        "<p style='color: var(--muted); font-style: italic;'>"
        "No messages yet — ask a question below to get started."
        "</p>",
        unsafe_allow_html=True,
    )

for msg in st.session_state.messages:
    avatar = ASSISTANT_AVATAR if msg["role"] == "assistant" else USER_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])


# ---------- Step 3/4: render a structured card ----------
def render_card(card):
    from response_cards import ClaimStatusCard, CoverageSummaryCard

    if isinstance(card, ClaimStatusCard):
        with st.container(border=True):
            st.markdown(f"**Claim {card.claim_id}**")
            cols = st.columns(3)
            cols[0].metric("Status", card.status)
            cols[1].metric("Amount", f"${card.amount:,.2f}")
            cols[2].metric("Date filed", card.date)

    elif isinstance(card, CoverageSummaryCard):
        with st.container(border=True):
            st.markdown(f"**{card.plan_name} — Coverage Summary**")
            cols = st.columns(3)
            cols[0].metric("Deductible", f"${card.deductible:,.0f}")
            cols[1].metric("Copay", f"{card.copay:.0f}%")
            cols[2].metric("Covered", "✅ Yes" if card.covered else "❌ No")


# ---------- Step 1 + 2: streaming input handling with citation capture ----------
def stream_chat_response(placeholder, session_id: str, member_id: str, message: str):
    """POST to /chat with stream=True, render tokens into `placeholder` as
    they arrive, and return (final_answer_text, citation_ids)."""
    full_text = ""
    first_token_received = False
    citation_ids = []

    placeholder.markdown("_Thinking..._")

    try:
        with requests.post(
            f"{API_URL}/chat",
            json={"session_id": session_id, "member_id": member_id, "message": message},
            stream=True,
            timeout=(5, 90),
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue

                payload = line[len("data: "):]

                if payload == "[DONE]":
                    break

                if payload.startswith("[CITATIONS]"):
                    ids_str = payload.replace("[CITATIONS]", "").strip()
                    citation_ids = [c for c in ids_str.split("|") if c]
                    continue

                if payload.startswith("[ERROR]"):
                    full_text = payload.replace("[ERROR]", "").strip()
                    placeholder.markdown(f"⚠️ {full_text}")
                    return full_text, citation_ids

                token = payload.replace("\\n", "\n")
                full_text += token
                first_token_received = True
                placeholder.markdown(full_text + "▌")

    except requests.exceptions.RequestException:
        error_msg = "Sorry, I lost connection to the coverage backend. Please try again."
        placeholder.markdown(f"⚠️ {error_msg}")
        return error_msg, citation_ids

    if not first_token_received and not full_text:
        full_text = "Sorry, I didn't get a response. Please try again."

    placeholder.markdown(full_text)
    return full_text, citation_ids


user_input = st.chat_input("Ask about your coverage...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        placeholder = st.empty()
        answer, citation_ids = stream_chat_response(
            placeholder,
            st.session_state.session_id,
            st.session_state.member_id,
            user_input,
        )

        # Step 4: render a structured card when the question clearly maps
        # to a claim lookup or a plan+procedure coverage check
        card = try_build_card(user_input)
        if card is not None:
            render_card(card)

        # Step 2: citations as an expandable "Policy sources" section
        if citation_ids:
            with st.expander(f"Policy sources ({len(citation_ids)})"):
                for cid in citation_ids:
                    st.markdown(f"- `{cid}`")

    st.session_state.messages.append({"role": "assistant", "content": answer})
