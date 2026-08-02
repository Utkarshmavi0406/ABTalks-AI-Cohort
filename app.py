"""
app.py
Day 17 — Chatbot Frontend Development
Streamlit chat UI that talks to the Day 16 FastAPI /chat backend.
"""

import uuid
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
API_URL = "http://localhost:8000"

st.set_page_config(page_title="Coverage Assistant", page_icon="⚕", layout="centered")

# ---------- Design system ----------
# A calm, trustworthy palette for a health-coverage context: deep teal accent
# against a cool off-white, avoiding both sterile hospital-blue and the
# generic warm-cream/terracotta AI-chat look.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --teal-900: #14312F;
    --teal-700: #2C6E6B;
    --teal-500: #4A9490;
    --teal-100: #E3F0EC;
    --bg: #F6F8F7;
    --card: #FFFFFF;
    --border: #DCE7E3;
    --text: #1F2A28;
    --muted: #66766F;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    font-family: 'Inter', sans-serif;
    color: var(--text);
}

[data-testid="stHeader"] {
    background: transparent;
}

/* Bottom chat-input bar: Streamlit renders this as a separate fixed
   container that doesn't inherit the main page background, so it needs
   its own explicit override or it shows the app's dark theme default. */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stChatInput"] {
    background: var(--bg) !important;
}
[data-testid="stBottom"] > div {
    background: var(--bg) !important;
    border-top: 1px solid var(--border);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--teal-100);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] label {
    font-family: 'Inter', sans-serif;
    color: var(--teal-900);
    font-weight: 600;
}

/* Title block */
.app-header {
    padding: 0.5rem 0 1.25rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.5rem;
}
.app-header h1 {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 2.4rem;
    color: var(--teal-900);
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
    background: linear-gradient(90deg, var(--teal-700), var(--teal-500));
    border-radius: 2px;
    margin-top: 0.6rem;
}

/* Chat bubbles */
[data-testid="stChatMessage"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.6rem;
    box-shadow: 0 1px 2px rgba(20, 49, 47, 0.04);
}

/* Chat input */
[data-testid="stChatInput"] {
    max-width: 760px;
    margin: 0 auto;
}
[data-testid="stChatInput"] > div {
    background: var(--card) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 3px rgba(20, 49, 47, 0.06);
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
    box-shadow: 0 0 0 2px rgba(74, 148, 144, 0.25) !important;
}

/* Buttons */
.stButton button {
    background: var(--card);
    color: var(--teal-700);
    border: 1px solid var(--teal-500);
    border-radius: 10px;
    font-weight: 500;
    transition: background 0.15s ease;
}
.stButton button:hover {
    background: var(--teal-100);
    border-color: var(--teal-700);
    color: var(--teal-900);
}

/* Session id badge */
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

/* Selectbox */
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
                  fill="#E3F0EC" stroke="#2C6E6B" stroke-width="2"/>
            <path d="M22 14 V28 M15 21 H29" stroke="#2C6E6B" stroke-width="3" stroke-linecap="round"/>
        </svg>
        <h1 style="margin:0;">Coverage Assistant</h1>
    </div>
    <p>Ask about your deductible, claims, or what's covered under your plan.</p>
    <div class="accent-rule"></div>
</div>
""", unsafe_allow_html=True)

ASSISTANT_AVATAR = "⚕"
USER_AVATAR = "🙂"

# ---------- Step 3: session_id, created once, persisted in session_state ----------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ---------- Step 4: message history, persisted across reruns ----------
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": "user"/"assistant", "content": str}

if "member_id" not in st.session_state:
    st.session_state.member_id = "M1001"  # placeholder; a real app would authenticate this


# ---------- Step 5: sidebar ----------
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


# ---------- Step 2: render the conversation thread ----------
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


# ---------- Step 3 + 4: handle new input ----------
user_input = st.chat_input("Ask about your coverage...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{API_URL}/chat",
                    json={
                        "session_id": st.session_state.session_id,
                        "member_id": st.session_state.member_id,
                        "message": user_input,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                answer = response.json()["answer"]
            except requests.exceptions.RequestException as e:
                answer = f"Sorry, I couldn't reach the coverage backend right now. ({e})"

        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
