"""Configure one experiment — selected questions × selected configurations ×
optional recency cutoff — and launch it as an eval.py subprocess (via runs.py).
Each question runs as its own dataset audience; there is deliberately no
audience override and no access-filter control. Call counts come from
eval.estimate_calls, not from rules duplicated here."""
import streamlit as st

import runs
from eval import (
    BASELINE_TOP_K,
    CANDIDATE_POOL_SIZE,
    MIN_RERANK_SCORE,
    RERANK_STATIC_TOP_K,
    estimate_calls,
    load_questions,
)
from models import CONFIG_NAMES

CONFIG_HELP = {
    "baseline": f"vector top-{BASELINE_TOP_K}",
    "filter-only": f"subject filter · vector top-{BASELINE_TOP_K}",
    "rerank-only": f"pool {CANDIDATE_POOL_SIZE} · rerank · top-{RERANK_STATIC_TOP_K}",
    "filter + rerank static": f"subject filter · pool {CANDIDATE_POOL_SIZE} · rerank · top-{RERANK_STATIC_TOP_K}",
    "filter + rerank dynamic": f"subject filter · pool {CANDIDATE_POOL_SIZE} · rerank · score ≥ {MIN_RERANK_SCORE}",
}
CUTOFF_CAVEAT = ("Dataset expectations (key facts, expected refusals) assume the full corpus; "
                 "with a cutoff, scores can drop because the evidence was excluded.")


def expectation(q: dict) -> str:
    return "refusal" if q["expect_refusal"] else "answer"


def _label(q: dict) -> str:
    preview = q["question"] if len(q["question"]) <= 60 else q["question"][:57] + "…"
    return f"**{q['id']}** · {q['audience']} · {expectation(q)} · {q.get('scenario', '—')} — {preview}"


def _set_questions(questions: list[dict], keep) -> None:
    for q in questions:
        st.session_state[f"q::{q['id']}"] = keep(q)


def render() -> None:
    questions = load_questions()

    st.markdown(f"**Evaluation dataset** · {len(questions)} canonical questions")
    st.caption("The audience comes from each test case: its expected result is defined for that role.")
    quick = st.columns(4)
    quick[0].button("All", on_click=_set_questions, args=(questions, lambda q: True))
    quick[1].button("None", on_click=_set_questions, args=(questions, lambda q: False))
    quick[2].button("Employee", on_click=_set_questions, args=(questions, lambda q: q["audience"] == "employee"))
    quick[3].button("Manager", on_click=_set_questions, args=(questions, lambda q: q["audience"] == "manager"))
    with st.container(height=260):
        chosen = [q for q in questions if st.checkbox(_label(q), key=f"q::{q['id']}", help=q["question"])]

    st.markdown("**Configurations** · the access filter is always on")
    configs = [name for name in CONFIG_NAMES
               if st.checkbox(f"{name} — {CONFIG_HELP[name]}", value=True, key=f"cfg::{name}")]

    cutoff = st.date_input("Updated on or after (optional)", value=None, key="run_cutoff",
                           help="Recency cutoff for every selected configuration: last_updated ≥ this date.")

    st.markdown("**Run summary**")
    if not chosen or not configs:
        st.caption("Select at least one question and one configuration.")
    else:
        st.markdown("\n".join(f"- {q['id']} ({q['audience']} · {expectation(q)})" for q in chosen))
        st.markdown(f"Configurations: {' · '.join(configs)}  \n"
                    f"Recency: {f'last_updated ≥ {cutoff.isoformat()}' if cutoff else 'none'} · "
                    f"Access filter: always on")
        st.markdown(f"Workload: {len(chosen)} questions × {len(configs)} configurations = "
                    f"{len(chosen) * len(configs)} answers · ≈ {estimate_calls(chosen, configs)} model calls")
        if cutoff:
            st.warning(CUTOFF_CAVEAT, icon=":material/history:")

    active = runs.active_run()
    confirmed = st.checkbox("I understand this run makes paid Bedrock calls", key="confirm_cost")
    if st.button("Run selected experiments", key="launch_run", type="primary", icon=":material/play_arrow:",
                 disabled=not (chosen and configs and confirmed) or active is not None):
        try:
            st.session_state["watching_run"] = runs.launch_run([q["id"] for q in chosen], configs, cutoff)
            del st.session_state["confirm_cost"]  # each run needs its own confirmation
        except runs.RunAlreadyActiveError:
            st.warning("A run is already in progress.")
        st.rerun()
    _status()


@st.fragment(run_every=5)
def _status() -> None:
    run_id = st.session_state.get("watching_run")
    if not run_id:
        return
    status = runs.run_status(run_id)
    if status == "running":
        with st.status(f"Running {run_id}…", state="running", expanded=True):
            st.code(runs.log_tail(run_id) or "starting…", language=None)
        return
    # Finished: stop watching and refresh the whole page so the runs table picks it up.
    del st.session_state["watching_run"]
    if status == "done":
        st.toast(f"Run {run_id} finished", icon=":material/check_circle:")
    else:
        st.toast(f"Run {run_id} failed — see its log", icon=":material/error:")
    st.rerun(scope="app")
