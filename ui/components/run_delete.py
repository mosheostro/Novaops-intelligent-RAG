"""Delete one saved run — only after an explicit confirmation tick, then
return to the (refreshed) runs list. Used by the run detail page and for
failed runs on the runs list."""
import streamlit as st

import runs


def render(run_id: str) -> None:
    with st.expander("Delete this run"):
        st.caption(f"Removes `runs/{run_id}.json` and its log. Datasets and other runs are not affected.")
        confirmed = st.checkbox(f"Delete {run_id} permanently", key=f"confirm_delete::{run_id}")
        if st.button("Delete run", key=f"delete_run::{run_id}", type="primary", icon=":material/delete:",
                     disabled=not confirmed):
            try:
                runs.delete_run(run_id)
            except (FileNotFoundError, runs.RunAlreadyActiveError) as e:
                st.error(str(e))
                return
            st.cache_data.clear()  # the detail page caches loaded runs by id
            st.switch_page("app_pages/eval_runs.py")
