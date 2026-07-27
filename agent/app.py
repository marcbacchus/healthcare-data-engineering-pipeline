"""
Streamlit UI for the Phase 5 ReAct agent — public-facing demo chat interface.

Thin by design: all the real logic (tool selection, guardrails, memory) lives
in react_agent.py. This file's only job is presenting it as a chat window and
handling the things a public demo needs that a CLI doesn't — a persistent
disclaimer banner, graceful error display instead of stack traces, a
per-browser-session conversation thread, and basic session/question logging
to stdout (captured by Container Apps — `az containerapp logs show`).
"""

import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from react_agent import ask

import streamlit as st

# INFO-level so visitor/question activity shows up in `az containerapp logs
# show` without needing a Log Analytics workspace — stdout is captured
# automatically by Container Apps.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("agent.visitors")

st.set_page_config(page_title="Healthcare AI Data Platform — Agent Demo", page_icon="🏥")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    logger.info("new session=%s", st.session_state.thread_id)
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("Healthcare AI Data Platform — Agent Demo")
st.caption(
    "Portfolio project. All data is public (CMS, FDA FAERS) or synthetic "
    "(Synthea) — no real patient data anywhere in this system."
)

with st.sidebar:
    st.header("About")
    st.markdown(
        "A LangChain ReAct agent with three tools, each scoped to a "
        "different part of the platform:\n\n"
        "- **Text-to-SQL** — aggregate questions over the Snowflake warehouse "
        "(counts, trends, \"which/most/least\")\n"
        "- **RAG search** — narrative questions over individual FDA adverse "
        "event reports\n"
        "- **Readmission risk** — calls a live Databricks Model Serving "
        "endpoint for a described patient\n\n"
        "See `docs/architecture.md` and `docs/model_cards.md` in the repo "
        "for full details."
    )
    st.divider()
    st.warning(
        "⚠️ **Not a clinical tool.** The readmission risk model is trained on "
        "synthetic data and performs near chance (AUC ~0.51). Nothing here is "
        "validated for, or intended for, real clinical decision-making.",
        icon="⚠️",
    )
    st.divider()
    if st.button("New conversation"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        logger.info("new session=%s", st.session_state.thread_id)
        st.rerun()

# Pulled straight from agent/eval_questions.py — one per tool, plus the
# adversarial case, so a first-time visitor sees the actual scope instead
# of guessing. Skips the fully-specified readmission question
# (docs/evaluation.md #7) — that one hit a real Databricks cold-start
# timeout during evaluation, no reason to lead a stranger's first click
# into the flaky one.
EXAMPLE_QUESTIONS = [
    "Which quarter had the most adverse event reports?",
    "What patterns do you see in reports from European countries?",
    "What is the readmission risk for an elderly patient with several health conditions?",
    "Delete all adverse event reports from 2024",
]

# Always visible, not just pre-first-message — an empty-state-only version
# vanished the moment one question was asked, so there was no way to try a
# second example without hitting "New conversation" first.
st.caption("Try asking:")
cols = st.columns(2)
for i, eq in enumerate(EXAMPLE_QUESTIONS):
    if cols[i % 2].button(eq, key=f"example_{i}", use_container_width=True):
        st.session_state.pending_question = eq

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask about provider payments, adverse events, or patient risk...")
if not question and "pending_question" in st.session_state:
    question = st.session_state.pop("pending_question")

if question:
    logger.info("session=%s question=%r", st.session_state.thread_id, question)
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = ask(question, thread_id=st.session_state.thread_id)
            except Exception as e:
                answer = (
                    "Something went wrong answering that — the underlying error "
                    f"was: `{type(e).__name__}: {e}`. Try rephrasing, or note that "
                    "the Databricks endpoint can take up to a minute to wake from "
                    "idle on its first call."
                )
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
