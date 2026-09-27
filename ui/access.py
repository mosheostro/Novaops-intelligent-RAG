"""Deployment boundary of the Streamlit UI — and ONLY the UI.

1. Secrets bridge. Streamlit Community Cloud provides configuration through
   st.secrets, while config.py (framework-independent) reads os.environ. Before
   config is imported, bridge_secrets() copies the config.py variables from
   st.secrets into os.environ — only where the environment has no value yet, so
   precedence is: shell environment > local .env > Streamlit secrets.
2. Password gate. APP_PASSWORD (from the environment/.env or st.secrets) is
   mandatory for every UI run; missing or blank fails closed. It is never
   copied into os.environ and never logged or displayed. This is basic demo
   protection, not user authentication — the sidebar role is still only a demo
   retrieval-audience selector.

Nothing here is imported by the RAG core, eval.py or tests of it: CLI and
backend use never need APP_PASSWORD.
"""
import hmac
from collections.abc import Mapping, MutableMapping

import streamlit as st
from dotenv import find_dotenv, load_dotenv

# config.py's contract: its six REQUIRED variables plus the optional ones.
CONFIG_KEYS = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION",
    "BEDROCK_MODEL_ID", "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION",
    "OPENSEARCH_AWS_ACCESS_KEY_ID", "OPENSEARCH_AWS_SECRET_ACCESS_KEY", "OPENSEARCH_ENDPOINT",
)
PASSWORD_KEY = "APP_PASSWORD"
AUTH_STATE_KEY = "authenticated"


def load_local_env() -> None:
    # Same call config.py makes; done first so a local .env outranks Cloud secrets.
    load_dotenv(find_dotenv())


def read_secrets() -> Mapping[str, object]:
    try:
        return st.secrets.to_dict()
    except FileNotFoundError:  # StreamlitSecretNotFoundError: no secrets.toml (a normal local run)
        return {}


def _value(source: Mapping[str, object], key: str) -> str | None:
    value = source.get(key)
    return value if isinstance(value, str) and value.strip() else None


def bridge_secrets(secrets: Mapping[str, object], environ: MutableMapping[str, str]) -> list[str]:
    """Copy config.py variables from `secrets` into `environ` where the
    environment has no (non-blank) value. Returns the NAMES filled, never values."""
    filled = []
    for key in CONFIG_KEYS:
        value = _value(secrets, key)
        if value is not None and _value(environ, key) is None:
            environ[key] = value
            filled.append(key)
    return filled


def configured_password(secrets: Mapping[str, object], environ: Mapping[str, str]) -> str | None:
    """The configured APP_PASSWORD (environment/.env first, then secrets), or None
    when it is missing, empty or whitespace-only."""
    return _value(environ, PASSWORD_KEY) or _value(secrets, PASSWORD_KEY)


def password_matches(candidate: str, expected: str) -> bool:
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))  # constant time


def require_login(expected: str | None) -> None:
    """Render the login screen and stop the script until this session has signed
    in. Fails closed when no password is configured."""
    if expected is None:
        st.error("Configuration error: APP_PASSWORD is not set. Add it to Streamlit secrets "
                 "(deployment) or to your local .env. The dashboard does not run without it.",
                 icon=":material/lock:")
        st.stop()
    if st.session_state.get(AUTH_STATE_KEY):
        return
    st.title("NovaOps Intelligent RAG")
    with st.form("login"):
        candidate = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        if password_matches(candidate, expected):
            st.session_state[AUTH_STATE_KEY] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()
