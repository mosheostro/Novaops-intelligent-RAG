"""Questions × configurations grid for one metric; selecting a row picks the
question for the drill-down."""
import pandas as pd
import streamlit as st

from models import ConfigurationResult, ContentEvaluation, EvaluationResult, RefusalEvaluation

METRICS = ["Faithfulness", "Context relevance", "Completeness", "Refusal OK", "Chunks"]


def _value(cfg: ConfigurationResult, metric: str) -> float | None:
    ev = cfg.evaluation
    if metric == "Chunks":
        return cfg.n_chunks
    if metric == "Refusal OK":
        return float(ev.refusal_ok) if isinstance(ev, RefusalEvaluation) else None
    if not isinstance(ev, ContentEvaluation):
        return None
    return {"Faithfulness": ev.faithfulness, "Context relevance": ev.context_relevance,
            "Completeness": ev.completeness}[metric]


def render(result: EvaluationResult) -> str | None:
    """Returns the selected question id, or None."""
    metric = st.segmented_control("Metric", METRICS, default="Faithfulness", key="matrix_metric")
    metric = metric or "Faithfulness"
    ids = list(result.questions)
    configs = result.metadata.configs
    df = pd.DataFrame([
        {"Question": qid, "Expected": "refusal" if q.expect_refusal else "answer",
         **{name: _value(q.configurations[name], metric) for name in configs}}
        for qid, q in result.questions.items()
    ])
    if metric == "Refusal OK":
        st.caption("Refusal OK is judged only for expected-refusal cases; answerable cases are empty.")
    elif metric != "Chunks":
        st.caption("Content judges are skipped for expected-refusal cases (empty cells); "
                   "choose Refusal OK to see those.")
    column = (st.column_config.NumberColumn(format="%d") if metric == "Chunks"
              else st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"))
    event = st.dataframe(
        df, hide_index=True, key="question_matrix", on_select="rerun", selection_mode="single-row",
        column_config={name: column for name in configs},
    )
    rows = event.selection.rows
    return ids[rows[0]] if rows else None
