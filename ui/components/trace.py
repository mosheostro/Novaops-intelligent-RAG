"""What the pipeline did: subject filter, the whole candidate pool, what got selected."""
import pandas as pd
import streamlit as st

from eval import MIN_RERANK_SCORE, RERANK_STATIC_TOP_K
from models import RetrievalResult, SelectionResult


def render(config: str, retrieval: RetrievalResult, selection: SelectionResult) -> None:
    if selection.status == "access_violation":
        st.markdown("**No retrieval:** the role is not a supported audience, so the request was rejected "
                    "before planning, search or reranking.")
        return
    subjects = retrieval.subjects_applied
    if subjects is None:
        st.markdown("**Subject filter:** not used by this configuration")
    elif not subjects:
        st.markdown("**Subject filter:** planner found no subjects — search ran unfiltered (fail-open)")
    else:
        st.markdown("**Subject filter:** " + " ".join(f":orange-badge[{s}]" for s in subjects))

    cut = {"rerank-only": f"static top-{RERANK_STATIC_TOP_K}",
           "filter + rerank static": f"static top-{RERANK_STATIC_TOP_K}",
           "filter + rerank dynamic": f"rerank score ≥ {MIN_RERANK_SCORE}"}.get(config, "all retrieved")
    recency = f"last_updated ≥ {retrieval.cutoff.isoformat()}" if retrieval.cutoff else "none"
    st.caption(f"Pool: top-{retrieval.top_k_requested} by vector similarity · recency cutoff: {recency} · "
               f"selection: {cut}")

    final_rank = {sc.candidate.vector_rank: sc.final_rank for sc in selection.chunks}
    rows = [{
        "Vector rank": c.vector_rank + 1,
        "Source": c.source,
        "Audience": c.audience,
        "Vector score": c.vector_score,
        "Rerank score": c.rerank_score,
        "Selected": c.vector_rank in final_rank,
        "Final rank": final_rank[c.vector_rank] + 1 if c.vector_rank in final_rank else None,
    } for c in retrieval.candidates]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Final rank"] = df["Final rank"].astype("Int64")  # unselected rows show empty, not the text "None"
    st.dataframe(
        df, hide_index=True,
        column_config={
            "Vector score": st.column_config.NumberColumn(format="%.3f"),
            "Rerank score": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
        },
    )
