"""Cards for the chunks that were actually sent to the model.

Chunk text is raw corpus markdown — a chunk that starts at the top of a
document begins with "# Title". It is therefore shown as plain text in a
bounded, scrollable box, never through st.markdown, so it can never render as
a heading. The full text stays available (scroll), nothing is truncated.
"""
import streamlit as st

from models import SelectionResult

CHUNK_BOX_HEIGHT = 160


def render(selection: SelectionResult) -> None:
    if not selection.chunks:
        st.caption("No chunks were selected — the answer was generated without evidence.")
        return
    for chunk in selection.chunks:
        c = chunk.candidate
        with st.container(border=True):
            rerank = "—" if c.rerank_score is None else f"{c.rerank_score:.2f}"
            st.markdown(f"**{chunk.final_rank + 1}. `{c.source}`** · {c.corpus} · :gray-badge[{c.audience}]")
            st.caption(
                f"subjects: {', '.join(c.subjects) or '—'} · updated {c.last_updated} · "
                f"vector {c.vector_score:.3f} · rerank {rerank}"
            )
            with st.container(height=CHUNK_BOX_HEIGHT, border=False):
                st.text(c.text)
