"""Screen 3 — one saved evaluation run: summary, per-question matrix, drill-down."""
import streamlit as st

import runs
from models import EvaluationResult
from ui.components import answer_card, judge_panel, question_matrix, run_delete, sources, summary_table, trace
from ui.components.run_launcher import CUTOFF_CAVEAT


@st.cache_data(show_spinner=False)
def _load(run_id: str) -> EvaluationResult:
    return runs.load_run(run_id)  # saved runs never change, so caching by id is safe


run_id = st.query_params.get("run")
st.page_link("app_pages/eval_runs.py", label="All runs", icon=":material/arrow_back:")
if not run_id or runs.run_status(run_id) != "done":
    st.info("**No evaluation run selected**  \nOpen an evaluation run from the Runs page to view its details.",
            icon=":material/info:")
    st.stop()

result = _load(run_id)
meta = result.metadata
st.title("Run detail")
st.caption(run_id)
for col, (label, value) in zip(st.columns(6), [
    ("Questions", meta.question_count), ("Configurations", len(meta.configs)),
    ("Cutoff", meta.cutoff.isoformat() if meta.cutoff else "none"), ("Baseline top-k", meta.baseline_top_k),
    ("Rerank pool / static top-k", f"{meta.candidate_pool_size} / {meta.static_top_k}"),
    ("Dynamic threshold", meta.dynamic_threshold),
]):
    col.metric(label, value)
if meta.cutoff:
    st.warning(f"Recency cutoff last_updated ≥ {meta.cutoff.isoformat()} was applied. {CUTOFF_CAVEAT}",
               icon=":material/history:")

st.subheader("By configuration")
summary_table.render(result.summary)

st.subheader("By question")
st.caption("Select a row to inspect that question.")
selected = question_matrix.render(result) or next(iter(result.questions), None)
if selected is None:
    st.stop()

q = result.questions[selected]
st.subheader(f"{q.id}: {q.question}")
st.markdown(
    f":violet-badge[{q.audience}] "
    + (":red-badge[expects refusal]" if q.expect_refusal else ":green-badge[answerable]") + " "
    + (" ".join(f":orange-badge[{s}]" for s in q.planned_subjects) if q.planned_subjects is not None
       else ":gray-badge[planner not run]")
)
if q.key_facts:
    st.caption("Key facts: " + " · ".join(q.key_facts))

for tab, name in zip(st.tabs(meta.configs), meta.configs):
    cfg = q.configurations[name]
    with tab:
        answer_card.render(name, cfg.retrieval, cfg.selection, cfg.answer)
        judge_panel.render(cfg.evaluation)
        with st.expander(f"Sources ({cfg.n_chunks})"):
            sources.render(cfg.selection)
        with st.expander("Pipeline trace"):
            trace.render(name, cfg.retrieval, cfg.selection)

st.divider()
run_delete.render(run_id)
