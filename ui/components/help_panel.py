"""Short usage guide shown in the sidebar on every page."""
import streamlit as st

from eval import BASELINE_TOP_K, CANDIDATE_POOL_SIZE, MIN_RERANK_SCORE, RERANK_STATIC_TOP_K

HELP = f"""
**What this is.** An inspectable RAG dashboard over the NovaOps handbook and manager playbook: ask questions,
see exactly how each answer was retrieved, and compare retrieval strategies.

**Chat vs Evaluation runs.** *Chat* answers one custom question as the role picked in the sidebar (a demo
switch, not authentication). *Evaluation runs* score preset test cases from `data/eval_questions.jsonl`,
each run as its own dataset audience.

**The five configurations** (the access filter is always on):
- `baseline` — vector top-{BASELINE_TOP_K}
- `filter-only` — subject filter · vector top-{BASELINE_TOP_K}
- `rerank-only` — pool {CANDIDATE_POOL_SIZE} · rerank · top-{RERANK_STATIC_TOP_K}
- `filter + rerank static` — subject filter · pool {CANDIDATE_POOL_SIZE} · rerank · top-{RERANK_STATIC_TOP_K}
- `filter + rerank dynamic` — subject filter · pool {CANDIDATE_POOL_SIZE} · rerank · every chunk scoring ≥ {MIN_RERANK_SCORE}; none → "no evidence"

**Updated on or after (cutoff).** Optional. Only documents with `last_updated` on or after the date are
searched. It narrows every configuration; it never replaces the access filter.

**Score with judges.** Chat only (+4 Bedrock calls): faithfulness, context relevance, refusal detection and
*Completeness (vs. retrieved context)* — how fully the answer uses what the retrieved context offers. It is a
different metric from the evaluation runs' *Completeness*, which checks the dataset's key facts; the two are
never mixed. With no usable context (no selected chunks, or a refusal) it is skipped: n/a, no extra call.

**Refusal / Refusal OK.** Some test cases *expect* a refusal (no allowed evidence). A refusal judge reads the
answer and decides whether it actually refused; *Refusal OK* means it did. Content judges are skipped for
those cases. In Chat the same judge shows *Refusal: Yes / No* — detected behavior only; there is no
Refusal OK because a custom question has no expected behavior.

**Sources / Pipeline trace.** Under each answer: *Sources* lists the chunks sent to the model (full text
scrolls in its box); *Pipeline trace* shows the subject filter, cutoff, the whole candidate pool with vector
and rerank scores, and which chunks were selected.

**Evaluation runs.** Pick test cases, configurations and an optional cutoff; check the run summary; confirm;
the run executes as a separate process and appears under *Saved runs*. Open a finished run for the summary,
the questions × configurations grid and per-question drill-down.

:orange[**Cost:** Chat answers, judges and every evaluation run call AWS Bedrock and consume model
resources. Evaluation runs make many calls — check the estimate before confirming.]
"""


def render() -> None:
    with st.expander("Help"):
        st.markdown(HELP)
