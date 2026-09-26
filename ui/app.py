"""NovaOps UI entry point: `streamlit run ui/app.py` from the project root."""
import sys
from pathlib import Path

# `streamlit run` puts ui/ on sys.path, not the project root the pipeline modules live in.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402,F401  -- first: loads .env and stops on any missing variable

import streamlit as st  # noqa: E402

from retrieval import SUPPORTED_AUDIENCES  # noqa: E402
from ui.components import help_panel  # noqa: E402

st.set_page_config(page_title="NovaOps Assistant", page_icon=":material/support_agent:", layout="wide")

pages = st.navigation([
    st.Page("pages/chat.py", title="Chat", icon=":material/chat:", default=True),
    st.Page("pages/eval_runs.py", title="Evaluation runs", icon=":material/analytics:"),
    st.Page("pages/eval_run_detail.py", title="Run detail", icon=":material/table_view:", visibility="hidden"),
])

with st.sidebar:
    st.radio("Role", sorted(SUPPORTED_AUDIENCES), key="role", horizontal=True)
    st.caption("Demo role — not authentication. It selects the audience filter for Chat retrieval.")
    help_panel.render()

pages.run()
