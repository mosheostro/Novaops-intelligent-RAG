"""About / Architecture — a read-only visual summary of docs/project-overview.md
(the canonical description). Static content only: no backend call, no run data,
no session state. Help answers "how do I use it"; this page answers "what is it
and why is it built this way"."""
import streamlit as st

from ui.components import architecture_diagrams as diagrams

st.title("NovaOps Intelligent RAG")
st.markdown(
    "An engineering-focused retrieval-augmented generation system over a company knowledge base. "
    "It demonstrates controlled retrieval, role-based access boundaries, reranking, comparative "
    "evaluation and reliability invariants — on Amazon Bedrock and Amazon OpenSearch Serverless."
)
st.caption("Canonical architecture description: `docs/project-overview.md` in the repository.")

# --- What the system demonstrates -------------------------------------------------------------
st.header("What the system demonstrates", divider="gray")
CAPABILITIES = [
    (":material/route:", "Controlled RAG", "A staged pipeline in which every step has one job and a defined failure behavior."),
    (":material/shield:", "Access-aware retrieval", "The caller's role limits what can be retrieved, inside the search itself."),
    (":material/sort:", "Reranking", "A wide candidate pool is re-scored by a language model before context is chosen."),
    (":material/analytics:", "Evaluation", "Pipeline configurations compared side by side with the same questions and judges."),
    (":material/verified:", "Reliability", "Security invariants and pipeline wiring covered by an offline test suite."),
    (":material/hub:", "Extensible architecture", "Clients attach at an application boundary, not to the retrieval internals."),
]
for row in (CAPABILITIES[:3], CAPABILITIES[3:]):
    for col, (icon, name, text) in zip(st.columns(3), row):
        with col.container(border=True, height="stretch"):
            st.markdown(f"**{icon} {name}**")
            st.caption(text)

# --- High-level architecture ------------------------------------------------------------------
st.header("High-level architecture", divider="gray")
st.markdown(
    "Clients stay thin. They call a small set of use cases at the application boundary, which drive a "
    "UI-independent RAG core. Evaluation uses the same pipeline and adds independent judges."
)
st.mermaid_chart(diagrams.ARCHITECTURE)
st.caption("Solid lines: implemented. Dashed: future clients, not implemented.")

# --- RAG pipeline -----------------------------------------------------------------------------
st.header("RAG pipeline", divider="gray")
st.mermaid_chart(diagrams.PIPELINE)
st.markdown(
    "- The role is checked **before** any model call; an unsupported role never reaches the index.\n"
    "- All filters run **inside** the vector query, so excluded content is never ranked.\n"
    "- Reranking and selection are separate: the reranker scores, selection decides how much becomes context.\n"
    "- With no candidate above the dynamic threshold, zero chunks are selected — no guessed context."
)

# --- Security vs relevance --------------------------------------------------------------------
st.header("Security vs relevance", divider="gray")
security, relevance = st.columns(2)
with security.container(border=True, height="stretch"):
    st.markdown("**:material/shield: Security boundary**")
    st.markdown(
        "Access control decides **what the caller may retrieve**.\n\n"
        "- Mandatory on every path; never a tunable parameter\n"
        "- Employee: company-wide content · Manager: whole corpus\n"
        "- Unknown roles are rejected (fail closed)"
    )
with relevance.container(border=True, height="stretch"):
    st.markdown("**:material/tune: Quality / relevance**")
    st.markdown(
        "Subject and recency filters improve **what is most useful**.\n\n"
        "- Optional; they never grant or define access\n"
        "- Only narrow an already-authorized pool\n"
        "- Subject filter fails open: no confident subject, no restriction"
    )
st.mermaid_chart(diagrams.SECURITY)
st.info(
    "A security violation is treated as an invariant failure — an architectural defect to fix — "
    "and reported as a separate count. It is never averaged into a quality score.",
    icon=":material/info:",
)

# --- Evaluation -------------------------------------------------------------------------------
st.header("Evaluation", divider="gray")
st.markdown(
    "Five configurations isolate one mechanism at a time, with access control on in all of them. "
    "Results are shown as neutral side-by-side measurements — the purpose is comparison, not ranking."
)
st.mermaid_chart(diagrams.EVALUATION)
METRICS = [
    ("Faithfulness", "Is the answer supported by the selected context?"),
    ("Context relevance", "Is the selected context relevant to the question?"),
    ("Completeness", "Does the answer contain the test case's key facts?"),
    ("Refusal OK", "For cases that expect a refusal: did the model refuse?"),
    ("Security violations", "Access-invariant failures, counted separately."),
]
for col, (name, text) in zip(st.columns(len(METRICS)), METRICS):
    col.markdown(f"**{name}**")
    col.caption(text)

# --- Live chat vs evaluation runs -------------------------------------------------------------
st.header("Live chat vs evaluation runs", divider="gray")
chat, runs_mode = st.columns(2)
with chat.container(border=True, height="stretch"):
    st.markdown("**:material/chat: Live chat**")
    st.markdown(
        "Interactive, single-question exploration and demonstration.\n\n"
        "- Custom question · one configuration\n"
        "- Optional judges; refusal is *detected*, not scored\n"
        "- Kept only in the browser session"
    )
with runs_mode.container(border=True, height="stretch"):
    st.markdown("**:material/analytics: Evaluation runs**")
    st.markdown(
        "Controlled, repeatable experiments on the evaluation dataset.\n\n"
        "- Selected test cases × selected configurations\n"
        "- Scored against each case's expectation\n"
        "- Saved as an immutable run artifact"
    )
st.caption("Both modes run the same pipeline steps and produce the same result models.")

# --- Why Streamlit? ---------------------------------------------------------------------------
st.header("Why Streamlit?", divider="gray")
st.markdown("**Streamlit is the current presentation layer, not the RAG architecture itself.**")
diagram, reasons = st.columns([2, 3], vertical_alignment="center")
with diagram:
    st.mermaid_chart(diagrams.STREAMLIT)
with reasons:
    st.markdown(
        "- The system is Python end to end; the UI calls the application layer in-process.\n"
        "- The goal is demonstrating RAG engineering and evaluation, not a consumer frontend.\n"
        "- No separate frontend stack, API contract or build pipeline to maintain.\n"
        "- The UI stays a thin presentation and evaluation layer.\n"
        "- The RAG core has no Streamlit dependency — the CLI already uses it without one.\n"
        "- The MCP server already uses the same boundary; an HTTP API would too."
    )
fits, later = st.columns(2)
with fits.container(border=True, height="stretch"):
    st.markdown("**Streamlit fits this project now**")
    st.markdown(
        "- Application and AI logic are already Python\n"
        "- Focus on AI engineering and evaluation\n"
        "- No complex consumer-grade UI needed\n"
        "- One stack keeps the project focused"
    )
with later.container(border=True, height="stretch"):
    st.markdown("**Next.js / React would fit a production web product**")
    st.markdown(
        "- Complex client-side state and interactions\n"
        "- Richer routing and frontend-specific UX\n"
        "- A dedicated frontend/backend split\n"
        "- Larger-scale, multi-user product requirements"
    )
st.markdown(
    "Streamlit is an intentional choice for the current project stage and purpose. "
    "It is not a fundamental dependency of the RAG architecture."
)

# --- Current architecture and future extensions -----------------------------------------------
st.header("Current architecture and future extensions", divider="gray")
st.mermaid_chart(diagrams.EXTENSIONS)
st.markdown(
    ":green-badge[Streamlit UI — implemented] :green-badge[MCP — implemented (STDIO · Streamable HTTP)] "
    ":gray-badge[HTTP API — future extension point]"
)
st.caption("Every client calls the same use cases and returns the same domain models; none bypass the core.")

# --- MCP integration --------------------------------------------------------------------------
st.header("MCP integration", divider="gray")
st.mermaid_chart(diagrams.MCP)
st.markdown(
    "An MCP server exposes the knowledge base to MCP-compatible clients such as MCP Inspector or Claude Code, "
    "over STDIO or Streamable HTTP. It offers three tools — ask a question, check knowledge-base health, "
    "describe its capabilities — and the subject vocabulary as a resource. It reuses the existing application "
    "boundary and RAG core: access control is still enforced inside the core, and responses carry answers and "
    "source metadata only, never document text or infrastructure details. The dashboard's MCP server page is "
    "itself an MCP client: it connects to a separately running server and never starts or manages it."
)
st.caption(
    "The server runs with a role fixed at startup (employee or manager) — a server setting, not "
    "authentication of the MCP caller. Caller authentication is not implemented, so the HTTP transport "
    "accepts local (loopback) connections only."
)

# --- Technology stack -------------------------------------------------------------------------
st.header("Technology stack", divider="gray")
STACK = [
    ("UI", "Streamlit"),
    ("Application / runtime", "Python · Pydantic domain models"),
    ("AI", "Amazon Bedrock · Nova chat model · Titan embeddings"),
    ("Retrieval", "Amazon OpenSearch Serverless (k-NN)"),
    ("Evaluation", "LLM-as-judge · saved JSON runs"),
    ("Cloud", "AWS"),
]
for col, (area, tech) in zip(st.columns(len(STACK)), STACK):
    col.caption(area)
    col.markdown(f"**{tech}**")

# --- Architecture principles ------------------------------------------------------------------
st.header("Architecture principles", divider="gray")
PRINCIPLES = [
    "UI-independent RAG core",
    "Explicit application boundary",
    "Security before retrieval",
    "Access control separated from relevance filtering",
    "Retrieve wide, then rerank",
    "No confident evidence, no guessed context",
    "Explicit evaluation, not demo impressions",
    "Security invariants separated from quality metrics",
    "Shared domain contracts",
    "Controlled external service boundaries",
    "Testable components, fully offline tests",
    "Open to new interfaces",
]
left, right = st.columns(2)
half = (len(PRINCIPLES) + 1) // 2
left.markdown("\n".join(f"- {p}" for p in PRINCIPLES[:half]))
right.markdown("\n".join(f"- {p}" for p in PRINCIPLES[half:]))

# --- About the author -------------------------------------------------------------------------
st.header("About the author", divider="gray")
st.markdown(
    "Built as a portfolio and engineering demonstration project by **Moshe Ostrovsky**.  \n"
    ":material/mail: [MosheOstro@gmail.com](mailto:MosheOstro@gmail.com) · "
    ":material/link: [LinkedIn](https://www.linkedin.com/in/moshe-ostrovsky/) · "
    ":material/code: [GitHub](https://github.com/mosheostro/)"
)
