"""Mermaid sources for the About / Architecture page — a visual summary of
docs/project-overview.md, which stays the canonical architecture description.
Static text only: building these strings touches no backend."""
from eval import BASELINE_TOP_K, CANDIDATE_POOL_SIZE, MIN_RERANK_SCORE, RERANK_STATIC_TOP_K
from models import CONFIG_NAMES

# Shared look for every diagram, matching .streamlit/config.toml (Inter, indigo on slate).
_INIT = (
    '%%{init: {"theme": "base", "themeVariables": {"fontFamily": "Inter, sans-serif", "fontSize": "15px", '
    '"lineColor": "#64748B", "clusterBkg": "#F8FAFC", "clusterBorder": "#CBD5E1", "primaryColor": "#EEF2FF", '
    '"primaryBorderColor": "#4F46E5", "primaryTextColor": "#0F172A", "edgeLabelBackground": "#FFFFFF"}}}%%\n'
)
_STYLES = """
    classDef client fill:#EEF2FF,stroke:#4F46E5,color:#1E1B4B
    classDef app fill:#FFFFFF,stroke:#64748B,color:#0F172A
    classDef core fill:#E0E7FF,stroke:#4338CA,color:#1E1B4B
    classDef ext fill:#FFFFFF,stroke:#94A3B8,color:#0F172A
    classDef future fill:#FFFFFF,stroke:#94A3B8,stroke-dasharray:5 5,color:#64748B
    classDef security fill:#FFF7ED,stroke:#C2410C,color:#431407
    classDef quality fill:#F0FDF4,stroke:#15803D,color:#052E16
    classDef muted fill:#FFFFFF,stroke:#CBD5E1,color:#475569
"""


def _diagram(body: str) -> str:
    return _INIT + body + _STYLES


# Layered top to bottom: clients → application boundary → core / evaluation → services.
ARCHITECTURE = _diagram("""flowchart TB
    user(["User"])
    ui["Streamlit UI<br/>Chat · Evaluation runs · About"]
    cli["Evaluation CLI"]
    future["HTTP API · MCP<br/>future clients"]
    boundary["Application boundary<br/>ask one question · run an experiment · saved runs"]
    ragcore["RAG core<br/>access · planning · filtering · retrieval<br/>reranking · selection · answer"]
    evaluation["Evaluation<br/>LLM judges · saved run artifacts"]
    search[("Amazon OpenSearch Serverless<br/>vector index")]
    bedrock["Amazon Bedrock<br/>embeddings + chat model"]
    user --> ui
    ui --> boundary
    cli --> boundary
    future -.->|not implemented| boundary
    boundary --> ragcore
    boundary -->|evaluation path| evaluation
    evaluation -->|same pipeline| ragcore
    ragcore --> search
    ragcore --> bedrock
    evaluation --> bedrock
    class ui,cli client
    class boundary app
    class ragcore core
    class evaluation quality
    class search,bedrock ext
    class future future
    class user muted
""")

# Two lanes linked subgraph-to-subgraph, so each lane keeps its left-to-right direction.
PIPELINE = _diagram(f"""flowchart TB
    subgraph retrieve["1 · Authorize and retrieve"]
        direction LR
        question(["Question + role"]) --> access{{"Access / role"}}
        access -->|unsupported| rejected["Rejected<br/>fail closed"]
        access -->|supported| planning["Planning<br/>subjects"]
        planning --> filtering["Filtering<br/>access + optional subject / recency"]
        filtering --> retrieval["Vector retrieval<br/>filters inside the query"]
    end
    subgraph answer_lane["2 · Rank, select and answer"]
        direction LR
        pool["Candidate pool<br/>{BASELINE_TOP_K} or {CANDIDATE_POOL_SIZE} chunks"] --> rerank["Optional reranking<br/>listwise LLM"]
        rerank --> selection["Context selection<br/>all · top {RERANK_STATIC_TOP_K} · score ≥ {MIN_RERANK_SCORE}"]
        selection --> answer(["Answer generation<br/>grounded in context"])
    end
    retrieve --> answer_lane
    class access,rejected security
    class planning quality
    class filtering app
    class retrieval,pool,rerank,selection core
    class question,answer client
""")

SECURITY = _diagram("""flowchart LR
    role(["Caller role"]) --> policy{"Access policy"}
    policy -->|employee| employee["Company-wide content only"]
    policy -->|manager| manager["Whole corpus"]
    policy -->|anything else| denied["Rejected before retrieval"]
    employee --> authorized[("Authorized slice<br/>of the corpus")]
    manager --> authorized
    authorized --> relevance["Subject + recency filters<br/>narrow, never widen"]
    relevance --> candidates["Candidate pool"]
    candidates --> audit["Security audit<br/>of every candidate"]
    class policy,employee,manager,denied,authorized,audit security
    class relevance quality
    class role,candidates muted
""")

_CONFIG_DETAILS = {
    "baseline": f"vector top {BASELINE_TOP_K}",
    "filter-only": f"subject filter · vector top {BASELINE_TOP_K}",
    "rerank-only": f"pool {CANDIDATE_POOL_SIZE} · rerank · top {RERANK_STATIC_TOP_K}",
    "filter + rerank static": f"subject filter · pool {CANDIDATE_POOL_SIZE} · rerank · top {RERANK_STATIC_TOP_K}",
    "filter + rerank dynamic": f"subject filter · pool {CANDIDATE_POOL_SIZE} · rerank · score ≥ {MIN_RERANK_SCORE}",
}
_CONFIG_NODES = "\n".join(
    f'        c{i}["{name}<br/>{_CONFIG_DETAILS[name]}"]' for i, name in enumerate(CONFIG_NAMES, 1)
)
_CONFIG_IDS = ",".join(f"c{i}" for i in range(1, len(CONFIG_NAMES) + 1))
_CONFIG_ROW = " ~~~ ".join(f"c{i}" for i in range(1, len(CONFIG_NAMES) + 1))  # invisible links keep one row

# Top-to-bottom bands linked only subgraph-to-subgraph, so each band keeps its own LR direction.
EVALUATION = _diagram(f"""flowchart TB
    subgraph inputs["Experiment"]
        direction LR
        dataset[("Evaluation dataset<br/>question + role + expectation")] --> experiment["Selected cases<br/>× selected configurations"]
    end
    subgraph configurations["Five configurations · access control on in all"]
        direction LR
{_CONFIG_NODES}
        {_CONFIG_ROW}
    end
    subgraph measures["Measured per answer"]
        direction LR
        content["Faithfulness · Context relevance · Completeness<br/>when an answer is expected"]
        refusal["Refusal OK<br/>when a refusal is expected"]
        violations["Security violations<br/>invariant check, counted separately"]
        content ~~~ refusal ~~~ violations
    end
    inputs --> configurations
    configurations --> measures
    class dataset muted
    class experiment app
    class {_CONFIG_IDS} core
    class content,refusal quality
    class violations security
""")

STREAMLIT = _diagram("""flowchart TB
    streamlit["Streamlit UI<br/>thin presentation layer"] --> boundary["Application boundary"]
    cli["Evaluation CLI<br/>no Streamlit"] --> boundary
    boundary --> ragcore["RAG core<br/>no UI dependency"]
    class streamlit,cli client
    class boundary app
    class ragcore core
""")

EXTENSIONS = _diagram("""flowchart TB
    streamlit["Streamlit UI<br/>implemented"]
    api["HTTP API<br/>future extension point"]
    mcp["MCP server / tools<br/>planned"]
    streamlit --> boundary["Application boundary"]
    api -.-> boundary
    mcp -.-> boundary
    boundary --> ragcore["RAG core + shared domain models"]
    ragcore --> services[("OpenSearch Serverless + Amazon Bedrock")]
    class streamlit client
    class api,mcp future
    class boundary app
    class ragcore core
    class services ext
""")

ALL = {
    "architecture": ARCHITECTURE,
    "pipeline": PIPELINE,
    "security": SECURITY,
    "evaluation": EVALUATION,
    "streamlit": STREAMLIT,
    "extensions": EXTENSIONS,
}
