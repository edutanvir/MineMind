import os

import streamlit as st

from src.ai import guard
from src.ai.gemini_agent import ask  # importing loads .env
from src.ui.theme import inject_css

st.set_page_config(page_title="MineMind | Ask MineMind", page_icon="💬", layout="wide")
inject_css()

SOURCES = {
    "search_mines": "NRCan Map 900A (Open Government Licence - Canada)",
    "mines_near_place": "NRCan Map 900A (Open Government Licence - Canada)",
    "get_production_trend": "Statistics Canada Table 16-10-0019-01 (Statistics Canada Open Licence)",
}
EXAMPLES = [
    "Which mapped features are within 50 km of Sudbury?",
    "Find Ontario mine features associated with nickel and summarize the Ontario nickel production trend.",
    "Summarize Ontario nickel quantity produced and shipped over the last 3 years.",
    "Compare Ontario nickel and copper quantity produced over the last 24 months.",
    "What can these two datasets tell us, and what can't they tell us?",
]

st.title("Ask MineMind")
st.caption(
    "Gemini picks a read-only Python tool, the tool queries the Gold tables, and Gemini explains the result. "
    "Provincial Statistics Canada values are not mine-level, and the two datasets are not joined by mine."
)

if "chat" not in st.session_state:
    st.session_state.chat = []
    st.session_state.asked = 0

if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
    st.error(
    "GEMINI_API_KEY is not configured. "
    "Configure it as an environment secret in your deployment settings."
            )
    st.stop()


def render_assistant(message: dict) -> None:
    st.markdown(message["answer"])
    calls = message["tool_calls"]
    with st.expander(f"Tools used ({len(calls)})"):
        if not calls:
            st.warning("No tool was called, so this answer is not backed by the data.")
        for call in calls:
            st.markdown(f"**{call['tool']}** returned {call['rows']} row(s)"
                        + (f" - error: {call['error']}" if call["error"] else ""))
            st.json(call["args"], expanded=False)
    used = sorted({SOURCES[c["tool"]] for c in calls if c["tool"] in SOURCES})
    if used:
        st.caption("Sources used: " + "; ".join(used))


for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_assistant(msg)

if not st.session_state.chat:
    st.subheader("Try a question")
    for i, example in enumerate(EXAMPLES):
        if st.button(example, key=f"example_{i}", use_container_width=True):
            st.session_state.pending = example
            st.rerun()

question = st.chat_input("Ask about Canadian mines or monthly mineral production") \
    or st.session_state.pop("pending", None)

if question:
    with st.chat_message("user"):
        st.markdown(question)
    if st.session_state.asked >= guard.SESSION_LIMIT:
        st.warning(f"This demo allows {guard.SESSION_LIMIT} questions per session. Reload the page to start over.")
    elif not guard.take_daily_slot():
        st.warning("The demo has reached today's question limit. Please try again tomorrow.")
    else:
        st.session_state.asked += 1
        with st.chat_message("assistant"):
            with st.spinner("Querying the data..."):
                try:
                    result = ask(question)
                except Exception as exc:  # keep the page alive; do not echo details that may hold secrets
                    result = {"answer": f"Something went wrong ({type(exc).__name__}). Please try again.",
                              "tool_calls": []}
            message = {"role": "assistant", "answer": result["answer"], "tool_calls": result["tool_calls"]}
            render_assistant(message)
        st.session_state.chat += [{"role": "user", "content": question}, message]

st.caption("AI can make mistakes. Check the Tools used panel and the Data & Methods page.")
