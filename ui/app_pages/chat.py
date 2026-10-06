"""Screen 1 — ask NovaOps. Single-turn: each question is answered on its own;
the history below is for reference and is never sent to the model.

Layout: the controls stay at the top of the page; only the conversation
scrolls, inside a fixed-height container that auto-scrolls to the newest
message; the chat input is pinned to the bottom by Streamlit."""
import logging

import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError
from opensearchpy.exceptions import OpenSearchException

import ask
from models import CONFIG_NAMES, DEFAULT_CONFIG, AskResult
from ui.components import answer_card, judge_panel, sources, trace
from ui.components.safe_markdown import neutralize_links
from ui.state import get_client

logger = logging.getLogger(__name__)

CONVERSATION_HEIGHT = 560
SERVICE_ERRORS = (BotoCoreError, ClientError, OpenSearchException)

history: list[AskResult] = st.session_state.setdefault("history", [])


def _clear_chat() -> None:
    st.session_state["history"] = []  # this browser session's conversation only; settings are kept


def render_result(r: AskResult) -> None:
    answer_card.render(r.config, r.retrieval, r.selection, r.answer)
    if r.judgement is not None:
        judge_panel.render(r.judgement)
    with st.expander(f"Sources ({len(r.selection.chunks)})"):
        sources.render(r.selection)
    with st.expander("Pipeline trace"):
        trace.render(r.config, r.retrieval, r.selection)


st.title("Ask NovaOps")
st.caption("Answers come only from the employee handbook and, for managers, the manager playbook.")

cols = st.columns([3, 2, 2, 1], vertical_alignment="bottom")
config = cols[0].selectbox("Configuration", CONFIG_NAMES, index=CONFIG_NAMES.index(DEFAULT_CONFIG),
                           key="chat_config")
cutoff = cols[1].date_input("Updated on or after", value=None, key="chat_cutoff",
                            help="Optional. Only documents with last_updated on or after this date are searched.")
judge = cols[2].toggle("Score with judges (+4 Bedrock calls)", key="chat_judge",
                       help="Faithfulness, context relevance, completeness (vs. retrieved context) and refusal "
                            "detection. Completeness is skipped when there is no usable context.")
cols[3].button("Clear", key="clear_chat", icon=":material/delete_sweep:", on_click=_clear_chat,
               disabled=not history, help="Clear this conversation. Settings and saved runs are not affected.")

conversation = st.container(height=CONVERSATION_HEIGHT, autoscroll=True)
with conversation:
    if not history:
        st.caption("No messages yet. Ask a question below — each one is answered on its own, "
                   "as the role selected in the sidebar.")
    for past in history:
        with st.chat_message("user"):
            st.markdown(neutralize_links(past.question))
        with st.chat_message("assistant"):
            render_result(past)

if question := st.chat_input("Ask about time off, benefits, severance, managing your team…"):
    with conversation:
        with st.chat_message("user"):
            st.markdown(neutralize_links(question))
        with st.chat_message("assistant"):
            try:
                with st.spinner("Searching and answering…"):
                    result = ask.ask(get_client(), question, st.session_state["role"], config,
                                     judge=judge, cutoff=cutoff)
            except SERVICE_ERRORS:  # Bedrock / OpenSearch / network failures — not programming errors
                logger.exception("chat ask failed config=%s", config)  # details stay in the server log
                st.error("Could not answer this question: the model or search service failed. "
                         "Details are in the server log.", icon=":material/error:")
            else:
                history.append(result)
                st.rerun()  # redraw from history so the Clear button and empty state reflect it
