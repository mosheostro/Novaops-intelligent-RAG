"""The answer plus its status badges — shared by chat and run drill-down."""
import streamlit as st

from models import RetrievalResult, SelectionResult
from ui.components.safe_markdown import neutralize_links


def render(config: str, retrieval: RetrievalResult, selection: SelectionResult, answer: str) -> None:
    n = len(selection.chunks)
    if selection.status == "access_violation":  # rejected before retrieval: the boundary held
        access = ":orange-badge[:material/block: access denied]"
    elif retrieval.security.violation:
        access = ":red-badge[:material/gpp_bad: access violation]"
    else:
        access = ":green-badge[:material/verified_user: access ok]"
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
    if selection.status == "access_violation":
        st.info(f"Access denied: role {retrieval.audience!r} is not a supported audience. The request was "
                "rejected before retrieval (fail closed) — no search, no model call.",
                icon=":material/block:")
    if selection.status == "not_found":
        st.warning("No evidence above the rerank threshold — the answer was generated from no context.",
                   icon=":material/search_off:")
    st.markdown(neutralize_links(answer))  # no clickable internal/external links
