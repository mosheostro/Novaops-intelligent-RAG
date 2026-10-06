"""MCP server — the dashboard as an MCP CLIENT of an already running NovaOps MCP
server (Streamable HTTP). It demonstrates the protocol: discovery, the health tool
and ask_rag, each through mcp_client's synchronous facade — never through the RAG
core, and never by importing the MCP SDK or the server.

The page does not start, stop or supervise the server: the server is a separate
process, started on its own, with its own fixed role. Nothing is called when the
page opens; discovery happens on Connect / Refresh and is kept in session state.
Only loopback URLs are accepted — the HTTP transport has no authentication, and
the page must not become a way to send requests to other hosts.

Named mcp_page.py, not mcp.py: a module named `mcp` on sys.path would shadow the
MCP SDK package for anything run from this folder."""
import logging
from urllib.parse import urlsplit

import streamlit as st

from ui.components.safe_markdown import neutralize_links

logger = logging.getLogger("ui.app_pages.mcp_page")  # Streamlit runs page scripts as __main__

DEFAULT_URL = "http://127.0.0.1:8000/mcp"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")  # the hosts the server itself may bind to
READ_TIMEOUT = 120  # seconds: covers a slow ask_rag and a cold start; the SDK default (300 s) is too long here
START_COMMAND = "python mcp_server.py --transport streamable-http --role employee"

st.title("MCP server")
st.caption("This page is an MCP client: it talks to a separately running NovaOps MCP server over Streamable "
           "HTTP — discovery, health and questions all go through the MCP protocol, not through the dashboard's "
           "own RAG calls. It never starts or stops the server.")

try:
    import mcp_client
except ImportError:  # the MCP SDK is an optional dependency (requirements-mcp.txt)
    st.info("The MCP client is not available here: the optional MCP dependency is not installed. To try this page "
            "locally, run `pip install -r requirements-mcp.txt`, start a server with "
            f"`{START_COMMAND}`, and reload.", icon=":material/extension_off:")
    st.stop()

state = st.session_state


def _url_problem(url: str) -> str | None:
    """Why `url` cannot be used from this page, or None. Structural: parsed, never prefix-matched."""
    try:
        mcp_client.check_url(url)
    except mcp_client.InvalidServerUrlError as exc:
        return str(exc)
    if urlsplit(url).hostname not in LOOPBACK_HOSTS:
        return (f"only a local MCP server can be used from this page: the host must be one of "
                f"{', '.join(LOOPBACK_HOSTS)}.")
    return None


def _call(what: str, action):
    """Run one MCP call; on failure show a safe message and return None."""
    try:
        return action()
    except mcp_client.ServerUnavailableError as exc:
        st.warning(f"MCP server unavailable: {exc}", icon=":material/cloud_off:")
    except mcp_client.ToolCallError as exc:
        st.error(f"The MCP server returned an error: {neutralize_links(str(exc))}", icon=":material/error:")
    except Exception:  # a programming error, possibly wrapped in an ExceptionGroup: details to the log only
        logger.exception("MCP %s failed", what)
        st.error("Unexpected error while communicating with the MCP server. Details are in the server log.",
                 icon=":material/error:")
    return None


def _connect() -> None:
    url = state["mcp_url"].strip()
    for key in ("mcp_connection", "mcp_health_result", "mcp_answer"):  # a new connection starts clean
        state.pop(key, None)
    if problem := _url_problem(url):
        st.error(problem, icon=":material/link_off:")
        return
    with st.spinner("Connecting…"):
        described = _call("discovery", lambda: mcp_client.describe(url, read_timeout=READ_TIMEOUT))
    if described is not None:
        state["mcp_connection"] = {"url": url, **described}
    else:
        st.caption(f"Start a server in another terminal, e.g. `{START_COMMAND}`, then press Connect / Refresh.")


# --- Connection -------------------------------------------------------------------------------
st.header("Connection", divider="gray")
cols = st.columns([4, 1], vertical_alignment="bottom")
cols[0].text_input("MCP server URL", value=DEFAULT_URL, key="mcp_url",
                   help="A running NovaOps MCP server's Streamable HTTP endpoint. Local (loopback) servers only.")
connect_clicked = cols[1].button("Connect / Refresh", key="mcp_connect", icon=":material/sync:")
if connect_clicked:
    _connect()

connection = state.get("mcp_connection")
if connection is None:
    if not connect_clicked:
        st.caption(f"Not connected. Start a server separately, e.g. `{START_COMMAND}`, then press "
                   "Connect / Refresh. Nothing is called until you do.")
    st.stop()

capabilities = connection["capabilities"]
server_role = capabilities["role"]["configured"]
st.success(f"Connected to {connection['url']}", icon=":material/check_circle:")
server = connection["server"]
st.markdown(
    f"**Transport** `{connection['transport']}` · **Server** `{server['name']}` "
    f"version `{server['version'] or 'n/a'}` · **Server role** :violet-badge[{server_role}]"
)
st.caption(f"{capabilities['role']['note']} The dashboard's sidebar role does not control the MCP server role — "
           "it is fixed when the server process starts; a server per role uses its own port.")
sidebar_role = state.get("role")
if sidebar_role and sidebar_role != server_role:
    st.info(f"The sidebar role is {sidebar_role}, but this MCP server was started as {server_role}. Questions on "
            f"this page are answered as {server_role}; the sidebar role applies to the Chat page only.",
            icon=":material/info:")

# --- MCP surface ------------------------------------------------------------------------------
st.header("MCP surface", divider="gray")
left, right = st.columns(2)
left.markdown("**Tools**\n" + "\n".join(f"- `{name}`" for name in connection["tools"]))
right.markdown("**Resources**\n" + "\n".join(f"- `{uri}`" for uri in connection["resources"]))
st.markdown("**Subjects** " + " ".join(f":gray-badge[{s}]" for s in connection["subjects"]))
with st.expander("Capabilities (get_rag_capabilities)"):
    st.json(capabilities)

# --- Health -----------------------------------------------------------------------------------
st.header("Health", divider="gray")
if st.button("Run health check", key="mcp_health", icon=":material/monitor_heart:",
             help="Calls the health_check tool: a read-only status check of the knowledge base."):
    with st.spinner("Checking…"):
        health = _call("health check", lambda: mcp_client.check_health(connection["url"], read_timeout=READ_TIMEOUT))
    if health is not None:
        state["mcp_health_result"] = health
if (health := state.get("mcp_health_result")) is not None:
    def _yes_no(value):
        return "n/a" if value is None else ("Yes" if value else "No")
    metrics = [("Ready", _yes_no(health["ready"])), ("Collection state", health["collection_state"]),
               ("Index present", _yes_no(health["index_present"])),
               ("Chunks", "n/a" if health["chunk_count"] is None else health["chunk_count"]),
               ("Data plane reachable", _yes_no(health["data_plane_reachable"]))]
    for col, (label, value) in zip(st.columns(len(metrics)), metrics):
        col.metric(label, value)

# --- Ask through MCP --------------------------------------------------------------------------
st.subheader("Ask through MCP")
configurations = [c["name"] for c in capabilities["configurations"]]
with st.form("mcp_ask"):
    question = st.text_area("Question", key="mcp_question", max_chars=capabilities["options"]["question_max_chars"])
    form_cols = st.columns([3, 2, 2], vertical_alignment="bottom")
    config = form_cols[0].selectbox("Configuration", configurations, key="mcp_config",
                                    index=configurations.index(capabilities["default_configuration"]))
    cutoff = form_cols[1].date_input("Updated on or after", value=None, key="mcp_cutoff",
                                     help=capabilities["options"]["updated_on_or_after"])
    judge = form_cols[2].toggle("Score with judges", key="mcp_judge", help=capabilities["judgement"]["note"])
    submitted = st.form_submit_button("Ask through MCP", key="mcp_ask_submit", icon=":material/send:")
st.caption(":orange[Each question calls AWS Bedrock on the server; judges add more model calls.]")

if submitted:
    if not question.strip():
        st.warning("Enter a question first.", icon=":material/edit:")
    else:
        with st.spinner("Asking through MCP…"):
            answer = _call("ask_rag", lambda: mcp_client.ask(
                connection["url"], question, config=config, judge=judge, updated_on_or_after=cutoff,
                read_timeout=READ_TIMEOUT))
        if answer is not None:
            state["mcp_answer"] = answer

if (result := state.get("mcp_answer")) is not None:
    audit = result["security_audit"]
    st.markdown(f":blue-badge[{result['config']}] :violet-badge[{result['role']}] "
                f":gray-badge[status: {result['status']}] "
                f":gray-badge[{result['retrieval']['candidates_considered']} candidates considered]")
    if audit["violation"]:
        # The projection already withheld answer, sources and judgement; show only the audit.
        st.error(audit["explanation"], icon=":material/gpp_bad:")
        st.caption(f"Violating sources: {audit['violating_source_count']} (names are never sent over MCP).")
    else:
        if result["status"] == "not_found":
            st.info("not_found: no content above the relevance threshold for this role — a normal result, "
                    "not an error.", icon=":material/search_off:")
        st.markdown(neutralize_links(result["answer"]))  # no clickable links from model output
        if result["sources"]:
            st.dataframe([{**s, "subjects": ", ".join(s["subjects"])} for s in result["sources"]],
                         hide_index=True)
        else:
            st.caption("No sources were selected.")
        if (judgement := result["judgement"]) is not None:
            scores = [("Faithfulness", judgement["faithfulness"]),
                      ("Context relevance", judgement["context_relevance"]),
                      ("Completeness (vs. retrieved context)", judgement["completeness"]),
                      ("Refused", None)]
            for col, (label, value) in zip(st.columns(len(scores)), scores):
                if label == "Refused":
                    col.metric(label, "Yes" if judgement["refused"] else "No")
                else:
                    col.metric(label, "n/a" if value is None else f"{value:.2f}")
    with st.expander("Raw MCP response"):
        st.json(result)
