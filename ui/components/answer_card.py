"""The answer plus its status badges — shared by chat and run drill-down."""
import streamlit as st

from models import RetrievalResult, SelectionResult
from ui.components.safe_markdown import neutralize_links


def render(config: str, retrieval: RetrievalResult, selection: SelectionResult, answer: str) -> None:
    n = len(selection.chunks)
    access = (":red-badge[:material/gpp_bad: access violation]" if retrieval.security.violation
              else ":green-badge[:material/verified_user: access ok]")
    st.markdown(
        f":blue-badge[{config}] :violet-badge[{retrieval.audience}] "
        f":gray-badge[{n} chunk{'s' if n != 1 else ''}] {access}"
    )
    if retrieval.security.violation:
        st.error(
            "Security violation: this role's retrieval returned manager-only sources: "
            + ", ".join(retrieval.security.violating_sources),
            icon=":material/gpp_bad:",
        )
    if selection.status == "not_found":
        st.warning("No evidence above the rerank threshold — the answer was generated from no context.",
                   icon=":material/search_off:")
    st.markdown(neutralize_links(answer))  # no clickable internal/external links
