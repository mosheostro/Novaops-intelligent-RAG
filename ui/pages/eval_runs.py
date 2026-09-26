"""Screen 2 — configure and launch an experiment, and browse saved runs."""
import streamlit as st

import runs
from ui.components import run_delete, run_launcher, runs_table

st.title("Evaluation runs")

with st.container(border=True):
    st.subheader("New experiment")
    run_launcher.render()

st.subheader("Saved runs")
listed = runs.list_runs()
if not listed:
    st.info("No runs yet. Configure one above, or run `python eval.py --save`.")
else:
    chosen = runs_table.render(listed)
    st.caption("Select a finished run to open it. Experiment details appear once a run has saved its result.")
    if chosen is not None:
        if chosen.status == "done":
            st.switch_page("pages/eval_run_detail.py", query_params={"run": chosen.id})
        elif chosen.status == "failed":
            st.warning(f"Run {chosen.id} did not finish. Last log lines:")
            st.code(runs.log_tail(chosen.id) or "(no log)", language=None)
            run_delete.render(chosen.id)
        else:
            st.info(f"Run {chosen.id} is still running.")
