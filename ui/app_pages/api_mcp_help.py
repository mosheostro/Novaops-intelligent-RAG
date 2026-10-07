"""API & MCP Help — a user manual for the two external interfaces: the REST API and
the MCP server. Documentation only: it makes no HTTP or MCP call, starts no
process, holds no session state, and reads the same on the hosted dashboard. The
authoritative contracts stay with the servers themselves — the REST API's /docs
and /openapi.json, and MCP discovery (tools/list, resources/list)."""
import streamlit as st

QUESTION = "Does the company match my 401k contributions?"

st.title("API & MCP Help")
st.markdown(
    "Besides this dashboard, NovaOps answers questions for other programs through two interfaces: a **REST API** "
    "for any HTTP client, and an **MCP server** for AI agents and MCP tools. Both are separate local processes "
    "over the same application and RAG core, and both return the same public answer — answers and source "
    "metadata, never document text or infrastructure details."
)
st.info(
    "Run these commands on your own machine, from a clone of the repository. The servers listen on "
    "127.0.0.1 only, so a hosted dashboard cannot reach them — and this page does not connect to them.",
    icon=":material/terminal:",
)
st.caption(
    "This page is a manual only. The **MCP server page** in the navigation is the dashboard's one built-in demo "
    "client: it connects to an MCP server you started and asks through the protocol. The dashboard's own pages "
    "call the application in-process; none of them uses the REST API."
)

# --- Before you start -------------------------------------------------------------------------
st.header("Before you start", divider="gray")
st.code(
    ".venv\\Scripts\\Activate.ps1                # macOS / Linux: source .venv/bin/activate\n"
    "pip install -r requirements-api.txt        # REST API: FastAPI and uvicorn\n"
    "pip install -r requirements-mcp.txt        # MCP server: the MCP SDK",
    language="powershell",
)
st.markdown(
    "- Work from the project root, with `.env` configured as for the dashboard.\n"
    "- **The role is chosen when a server starts** (`--role employee` or `--role manager`) and applies to every "
    "request it serves; callers cannot change it. It is a server setting, not authentication — run one server "
    "per role.\n"
    "- **Loopback only, no authentication** in this version: servers accept connections from this machine only.\n"
    "- Asking a question calls the language model, so it costs model calls; health and discovery do not ask "
    "questions. The first question after an idle period can take noticeably longer."
)

# --- REST API ---------------------------------------------------------------------------------
st.header("REST API", divider="gray")
st.subheader("1 · Start a server per role")
st.code(
    "python api_server.py --role employee                 # http://127.0.0.1:8001\n"
    "python api_server.py --role manager --port 8002      # http://127.0.0.1:8002",
    language="powershell",
)
st.subheader("2 · Open the contract")
st.markdown(
    "Open **http://127.0.0.1:8001/docs** in a browser: the interactive OpenAPI page lists every endpoint with "
    "its request and response schema and lets you try them. `/openapi.json` is the same contract as JSON."
)
st.subheader("3 · Check liveness and readiness")
st.code(
    "curl.exe -s http://127.0.0.1:8001/healthz       # liveness: the process is up — no backend call\n"
    "curl.exe -s http://127.0.0.1:8001/v1/health     # readiness: checks the knowledge base — 200 ready, 503 not",
    language="powershell",
)
st.caption("`curl.exe` works in every PowerShell version; on macOS / Linux use `curl`.")
st.subheader("4 · Ask a question")
st.code(
    f'$body = @{{ question = "{QUESTION}" }} | ConvertTo-Json\n'
    "Invoke-RestMethod http://127.0.0.1:8001/v1/ask -Method Post -ContentType \"application/json\" -Body $body",
    language="powershell",
)
st.code(
    "curl -s http://127.0.0.1:8001/v1/ask -H \"Content-Type: application/json\" \\\n"
    f"     -d '{{\"question\": \"{QUESTION}\"}}'",
    language="bash",
)
st.markdown(
    "- Optional fields: `config`, `judge` and `updated_on_or_after` — see `/docs` for the full schema. A body "
    "that names a `role` is rejected (422).\n"
    "- The answer comes with its sources as metadata and a `security_audit`. Nothing relevant found "
    "(`not_found`) is a normal result, and so is a failed security audit: the answer and sources are withheld.\n"
    "- Errors are `application/problem+json` with fixed wording: 422 invalid input, 415 a body not sent as "
    "JSON, 503 the knowledge base or model service is unavailable, 504 it timed out."
)

# --- MCP server -------------------------------------------------------------------------------
st.header("MCP server", divider="gray")
st.subheader("1 · Choose a transport")
st.markdown(
    "| Transport | How it runs | Use it for |\n"
    "|---|---|---|\n"
    "| STDIO | The MCP client starts the server process itself and talks over its stdin/stdout | Agents and "
    "tools that launch servers (e.g. Claude Code) |\n"
    "| Streamable HTTP | You start the server; clients connect to `http://127.0.0.1:<port>/mcp` | Inspector, "
    "the dashboard's MCP server page, several clients at once |"
)
st.subheader("2 · Start a Streamable HTTP server per role")
st.code(
    "python mcp_server.py --transport streamable-http --role employee               # http://127.0.0.1:8000/mcp\n"
    "python mcp_server.py --transport streamable-http --role manager --port 8010    # http://127.0.0.1:8010/mcp",
    language="powershell",
)
st.subheader("3 · Try it with the project's client")
st.caption("No extra install. Each command is one MCP session against a running server.")
st.code(
    "python mcp_client.py discover --url http://127.0.0.1:8000/mcp     # identity, tools, resources, capabilities\n"
    "python mcp_client.py health --url http://127.0.0.1:8000/mcp\n"
    f'python mcp_client.py ask "{QUESTION}" --url http://127.0.0.1:8000/mcp\n'
    "python mcp_client.py discover --role employee     # STDIO: the client starts its own server",
    language="powershell",
)
st.subheader("4 · Explore with MCP Inspector (optional)")
st.caption("A third-party tool that needs Node.js; `npx` downloads it on first use. The command forms below "
           "were verified with MCP Inspector 2.9.0 against this server over Streamable HTTP.")
st.code(
    "npx @modelcontextprotocol/inspector     # web UI: connect with Streamable HTTP to http://127.0.0.1:8000/mcp\n"
    "npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --method tools/list\n"
    "npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --method tools/call "
    "--tool-name get_rag_capabilities\n"
    "npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --method tools/call "
    f'--tool-name ask_rag --tool-arg "question={QUESTION}"\n'
    "npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --method resources/read --uri rag://subjects",
    language="powershell",
)
st.markdown(
    "| Tool or resource | What it does |\n"
    "|---|---|\n"
    "| `ask_rag` | Answers one question as the server's role (optional configuration, judging and recency cutoff) |\n"
    "| `health_check` | Whether the knowledge base is ready |\n"
    "| `get_rag_capabilities` | The server's role, the answer configurations, judging and security behaviour |\n"
    "| `rag://subjects` | The subject vocabulary (a resource) |\n\n"
    "`tools/list` and `resources/list` return the exact schemas."
)

# --- REST or MCP? -----------------------------------------------------------------------------
st.header("REST or MCP?", divider="gray")
st.markdown(
    "| | REST API | MCP server |\n"
    "|---|---|---|\n"
    "| Typical client | curl, scripts, any HTTP client | AI agents, Claude Code, MCP Inspector |\n"
    "| Protocol | HTTP + JSON | JSON-RPC over STDIO or Streamable HTTP |\n"
    "| Discovery | `/docs`, `/openapi.json` | `tools/list`, `resources/list` |\n"
    "| Errors | HTTP status + problem+json | A tool error in the result |\n"
    "| Default port | 8001 | 8000 (`/mcp`) |\n\n"
    "Both: role fixed at startup, loopback only, no authentication, the same public answer."
)

# --- Troubleshooting --------------------------------------------------------------------------
st.header("Troubleshooting", divider="gray")
st.markdown(
    "- **Port already in use** — start the server with another `--port`.\n"
    "- **Slow first answer, or 503** — the knowledge base may be warming up; check readiness "
    "(`/v1/health` or `health_check`) and retry.\n"
    "- **REST 400** — the request did not use a loopback host name; use `127.0.0.1` or `localhost`.\n"
    "- **REST 415** — send the body with `Content-Type: application/json`.\n"
    "- **REST 422 naming `role`** — the role is chosen at startup, not per request.\n"
    "- **MCP 421** — the HTTP request carried a non-loopback `Host`; connect to `127.0.0.1`.\n"
    "- **A server exits at startup** — an unsupported `--role`, or a `--host` that is not loopback."
)

# --- Where the contracts live -----------------------------------------------------------------
st.header("Where the contracts live", divider="gray")
st.markdown(
    "- **REST API:** `/docs` (interactive) and `/openapi.json` on the running server.\n"
    "- **MCP server:** `tools/list` and `resources/list` — through `mcp_client.py discover` or Inspector.\n"
    "- **In the repository:** the *REST API* and *MCP server* sections of `README.md`, and "
    "`docs/architecture.md` §14–15."
)
