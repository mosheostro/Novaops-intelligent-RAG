"""Per-configuration averages for one evaluation run — neutral comparative
measurements: no best/winner highlighting, no ranking."""
import pandas as pd
import streamlit as st

from models import ConfigName, ConfigSummary


def render(summary: dict[ConfigName, ConfigSummary]) -> None:
    df = pd.DataFrame([{
        "Configuration": name,
        "Chunks (avg)": s.n_chunks_avg,
        "Faithfulness": s.faithfulness_avg,
        "Context relevance": s.context_relevance_avg,
        "Completeness": s.completeness_avg,
        "Refusal OK": s.refusal_ok_avg,
        "Security violations": s.security_violations,
        "Access violations": s.access_violations,
    } for name, s in summary.items()])
    violations = int(df["Security violations"].sum()) if not df.empty else 0
    if violations:
        # An invariant failure, not a quality result — flagged, never ranked.
        st.error(f"{violations} security violation(s) in this run — see the configurations below.",
                 icon=":material/gpp_bad:")
    score = st.column_config.NumberColumn(format="%.2f")
    st.dataframe(df, hide_index=True, column_config={
        "Chunks (avg)": st.column_config.NumberColumn(format="%.2f"),
        "Faithfulness": score, "Context relevance": score, "Completeness": score, "Refusal OK": score,
    })
    st.caption("Averages over the questions in this run. Refusal OK averages only the refusal cases; "
               "the other scores only the answerable ones. Empty = no question of that kind. "
               "Access violations = cases whose role is not supported, rejected before retrieval "
               "and excluded from every average.")
