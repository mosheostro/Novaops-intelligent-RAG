"""NovaOps UI entry point: `streamlit run ui/app.py` from the project root.

Lifecycle of every run: deployment boundary (secrets bridge + password gate)
→ backend configuration → shared sidebar (Role + Help) → navigation → page.
Page scripts live in ui/app_pages/, deliberately NOT ui/pages/: a `pages/`
folder next to this file turns on Streamlit's legacy auto-discovered pages,
which Streamlit falls back to whenever a run stops before st.navigation (the
login screen) — and it then runs a page file on its own, bypassing all of the
above.
"""
import logging
import os
import sys
from pathlib import Path

# `streamlit run` puts ui/ on sys.path, not the project root the pipeline modules live in.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from ui import access  # noqa: E402  -- Streamlit-only; imports nothing from the RAG core

st.set_page_config(page_title="NovaOps Assistant", page_icon=":material/support_agent:", layout="wide")

# 1. Deployment boundary, BEFORE anything of the RAG app is imported or run:
#    shell env > local .env > Streamlit secrets, then the mandatory password gate.
access.load_local_env()
_secrets = access.read_secrets()
access.bridge_secrets(_secrets, os.environ)
access.require_login(access.configured_password(_secrets, os.environ))

# 2. Backend configuration — validated now that the environment is complete.
try:
    import config  # noqa: F401
except RuntimeError as e:
    # Only config.ConfigError (a RuntimeError) is expected here. It cannot be
    # imported by name, because importing config is exactly what failed.
    if (type(e).__module__, type(e).__name__) != ("config", "ConfigError"):
        raise
    logging.getLogger(__name__).error("backend configuration invalid: %s", e)  # names only, never values
    st.error(f"Configuration error: {e}", icon=":material/settings:")  # ConfigError lists variable NAMES only
    st.stop()

from retrieval import SUPPORTED_AUDIENCES  # noqa: E402
from ui.components import help_panel  # noqa: E402

# 3. Shared, authenticated UI: the sidebar (and so st.session_state["role"]) exists
#    before navigation resolves and before any page reads it.
with st.sidebar:
    st.radio("Role", sorted(SUPPORTED_AUDIENCES), key="role", horizontal=True)
    st.caption("Demo role — not authentication. It selects the audience filter for Chat retrieval.")
    help_panel.render()

# 4. Navigation and the page.
pages = st.navigation([
    st.Page("app_pages/chat.py", title="Chat", icon=":material/chat:", default=True),
    st.Page("app_pages/eval_runs.py", title="Evaluation runs", icon=":material/analytics:"),
    st.Page("app_pages/eval_run_detail.py", title="Run detail", icon=":material/table_view:", visibility="hidden"),
    st.Page("app_pages/infrastructure.py", title="Infrastructure & Setup", icon=":material/dns:"),
    st.Page("app_pages/about.py", title="About / Architecture", icon=":material/account_tree:"),
])
pages.run()
