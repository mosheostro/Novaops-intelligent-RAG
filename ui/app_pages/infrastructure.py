"""Infrastructure & Setup — a read-only view of how the infrastructure and the
knowledge base were prepared and are managed. Runtime question answering lives
on About / Architecture; usage help stays in the sidebar. Static content only:
no backend call, no run data, no session state, no private infrastructure
details (the collection was provisioned outside this repository)."""
import streamlit as st

from ui.components import infrastructure_diagrams as diagrams

st.title("Infrastructure & Setup")
st.markdown(
    "How the infrastructure and the knowledge base behind the assistant were prepared, loaded and "
    "are managed — the work done *before* anyone asks a question. The runtime path is on "
    "**About / Architecture**."
)
st.caption("Concepts first, current technology in parentheses: vector store (Amazon OpenSearch Serverless), "
           "embedding and chat models (Amazon Bedrock).")

# --- Setup lifecycle --------------------------------------------------------------------------
st.header("Setup lifecycle", divider="gray")
st.markdown(
    "The vector store collection and model access are prerequisites provisioned outside this repository. "
    "From there, the repository creates the index, loads the corpus once, and can inspect or delete the "
    "collection — each step with its own script and its own guard."
)
st.subheader("Setup & runtime lifecycle")
st.mermaid_chart(diagrams.LIFECYCLE)
st.subheader("Collection administration")
st.mermaid_chart(diagrams.ADMINISTRATION)

# --- Knowledge-base ingestion -----------------------------------------------------------------
st.header("Knowledge-base ingestion", divider="gray")
st.markdown(
    "Each Markdown document carries a small header (audience, corpus, last-updated date). The header "
    "becomes metadata and is removed before chunking, so it is never embedded. Every chunk inherits its "
    "document's metadata and subject tags, then gets its own embedding."
)
st.mermaid_chart(diagrams.INGESTION)
SNAPSHOT = [("Documents", 32), ("Chunks", 400), ("All-staff chunks", 217), ("Manager-only chunks", 183),
            ("Vector dimensions", 1024), ("Subjects", 9)]
for col, (label, value) in zip(st.columns(len(SNAPSHOT)), SNAPSHOT):
    col.metric(label, value)
st.caption("Documented snapshot from the index verification recorded in the project documentation — "
           "static figures, not read live from the index.")

# --- Index fields and filtering ---------------------------------------------------------------
st.header("Index fields and filtering", divider="gray")
st.markdown(
    "| Field | Index type | Created from | Used when answering |\n"
    "|---|---|---|---|\n"
    "| `vector` | 1024-dim vector · HNSW · inner product | Titan embedding of the chunk | Similarity search |\n"
    "| `text` | Full text | The chunk (document body, header removed) | Context for the answer |\n"
    "| `audience` | Keyword | Document header: `all` or `manager` | **Access filter — security boundary**, "
    "mandatory, fails closed |\n"
    "| `subjects` | Keyword list | One Nova tag call per document, cached | Subject filter — relevance, "
    "fails open |\n"
    "| `last_updated` | Date | Document header | Optional recency cutoff — relevance |\n"
    "| `source`, `corpus` | Keyword | File name · header | Shown with the sources |"
)
st.caption("All filters run inside the vector search itself. Why access and relevance are treated "
           "differently is explained on About / Architecture.")

# --- Supporting scripts -----------------------------------------------------------------------
st.header("Supporting scripts", divider="gray")
SCRIPTS = [
    (":material/cable:", "client.py",
     "Shared connections: the embedding call and the vector-store client, which finds the collection by "
     "name. The only place the Bedrock client is created."),
    (":material/table_chart:", "create_index.py",
     "Creates the index and its field mapping when it is missing. Never deletes, recreates or changes an "
     "existing index."),
    (":material/upload_file:", "ingest.py",
     "Reads, chunks, tags, embeds and bulk-loads the corpus. Refuses a missing or already populated "
     "index; only ever adds records."),
    (":material/sell:", "subjects.py",
     "The fixed subject vocabulary shared by the tagger, the planner and the filter. Tags each document "
     "once and caches the result."),
    (":material/monitor_heart:", "manage.py",
     "Reports whether the collection exists, is active and how many chunks it holds; can delete it after "
     "a typed confirmation. Never creates it."),
    (":material/build:", "setup.sh · setup.ps1 · config.py",
     "Create the virtual environment and install dependencies without any cloud call; every required "
     "setting is validated at startup."),
]
for row in (SCRIPTS[:3], SCRIPTS[3:]):
    for col, (icon, name, text) in zip(st.columns(3), row):
        with col.container(border=True, height="stretch"):
            st.markdown(f"**{icon} `{name}`**")
            st.caption(text)

# --- Safeguards -------------------------------------------------------------------------------
st.header("Safeguards", divider="gray")
left, right = st.columns(2)
left.markdown(
    "- The index is only ever created, never replaced.\n"
    "- Ingestion checks the index before any model call and refuses to load a second copy.\n"
    "- Document headers are stripped before embedding — verified: none reached the index."
)
right.markdown(
    "- Subject tags are cached, so a re-run does not pay for tagging again.\n"
    "- Deleting the collection is a separate, deliberate command with a typed confirmation.\n"
    "- Credentials and collection details stay in local configuration, never in code or on this page."
)
