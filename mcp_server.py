"""MCP adapter for the NovaOps knowledge base — a thin transport layer over the
existing application use cases. It owns the MCP surface (tool/resource
declarations, schemas, the response models below) and nothing else: retrieval,
access control, reranking and judging all stay in the core, which never imports
this module or the MCP SDK.

    python mcp_server.py --role employee     # or: python -m mcp_server --role manager

The role is a SERVER role, fixed at startup and validated by retrieval's own
access_filter() — no default, no fallback. It selects the audience filter for
every request; it is not authentication and says nothing about who the MCP
client is: whoever launches the process chooses it.

STDIO transport: stdout carries the JSON-RPC protocol and nothing else. Logs go
to stderr (the SDK configures that); usage and startup errors go to stderr too.

Streamable HTTP is an additional transport over the same server — stateless,
plain JSON responses, endpoint http://<host>:<port>/mcp, loopback hosts only:

    python mcp_server.py --transport streamable-http --role employee [--port 8000]
"""
import argparse
import json
import logging
import threading
from collections.abc import Callable, Sequence
from datetime import date
from typing import Annotated, Literal, TypeVar

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

import config  # noqa: F401  -- validates the environment before any project module is imported

import ask
import client
import manage
from failures import FailureKind, classify_failure
from logging_setup import NOISY_THIRD_PARTY_LOGGERS
from manage import CollectionHealth
from models import CONFIG_NAMES, DEFAULT_CONFIG, AskResult, ConfigName, LiveJudgement
from retrieval import SUPPORTED_AUDIENCES, UnsupportedAudienceError, access_filter
from subjects import SUBJECTS

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 2000  # input / token-cost guard at the MCP boundary; not an ask() rule
CAPABILITIES_CONTRACT_VERSION = 1  # bumped only by a breaking change; new fields are additive
SUBJECTS_URI = "rag://subjects"
# The name every client receives in initialize -> serverInfo. A neutral public name —
# never derived from, or equal to, any infrastructure identifier (collection, index, ...).
SERVER_NAME = "novaops-knowledge-base"
# serverInfo.version: this server implementation's version, bumped by hand when the server
# changes. Independent of CAPABILITIES_CONTRACT_VERSION and of the MCP protocol version.
SERVER_VERSION = "0.2.0"
# Streamable HTTP: one fixed endpoint, bound to loopback only (there is no authentication).
# Exactly the hosts for which the SDK enables its DNS-rebinding protection on its own.
HTTP_PATH = "/mcp"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

# Fixed wording for a failed security audit: names the rule category only — never a
# file, a document or any of its text.
WITHHELD_ANSWER = ("The answer was withheld because a security check failed for this request. "
                   "Please report this to the system operator.")
SECURITY_VIOLATION_EXPLANATION = (
    "Access-control audit failed: retrieval returned content outside the audience permitted "
    "for the configured role. The answer, sources and judgement were withheld.")

# The MCP wording for each failure category (failures.py). "internal" has none on
# purpose: the SDK reports it as a bare "Error executing tool <name>".
_TOOL_ERRORS: dict[FailureKind, str] = {
    "unsupported_role": "unsupported_role: the server's configured role is not supported.",
    "service_unavailable": "service_unavailable: the knowledge base or model service is unavailable. "
                           "Try again later.",
    "service_timeout": "service_timeout: the knowledge base did not respond in time; it may be warming up. "
                       "Retry shortly.",
}

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_CHARS)]
UpdatedOnOrAfter = Annotated[date | None, Field(
    description="Optional ISO date, YYYY-MM-DD (e.g. 2025-01-31). Keeps only documents updated on or after it.")]

_SUBJECTS_JSON = json.dumps({"subjects": list(SUBJECTS)})  # static vocabulary — no I/O when read

T = TypeVar("T")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SourceRef(_Frozen):
    """A selected chunk's provenance — never its text."""
    rank: int
    source: str
    corpus: str
    subjects: list[str]
    last_updated: str
    rerank_score: float | None


class RetrievalInfo(_Frozen):
    candidates_considered: int  # observed pool size for this request, not a tuning value


class SecurityAuditView(_Frozen):
    """The public face of the domain SecurityAudit: whether it failed and how many
    sources it flagged — never which ones."""
    violation: bool
    violating_source_count: int
    explanation: str | None


class AskRagResult(_Frozen):
    answer: str
    config: ConfigName
    role: str
    status: Literal["selected", "not_found"]
    planned_subjects: list[str] | None
    cutoff: date | None
    retrieval: RetrievalInfo
    sources: list[SourceRef]
    security_audit: SecurityAuditView
    judgement: LiveJudgement | None


def project_ask_result(r: AskResult) -> AskRagResult:
    """The less-privileged MCP view of an AskResult: no chunk text, no vector
    scores, no question echo. When the security audit failed, everything that
    could carry protected content — the answer, the sources, the judges' reasons —
    is withheld, and only the count of violating sources is reported."""
    status = r.selection.status
    if status not in ("selected", "not_found"):
        # ask() raises for an unsupported role instead of returning this evaluation-only status.
        raise RuntimeError(f"unexpected selection status {status!r}")
    audit = r.retrieval.security
    violation = audit.violation
    if violation:
        logger.warning("ask_rag security audit failed: answer withheld, violating source count=%d",
                       len(audit.violating_sources))
    sources = [] if violation else [
        SourceRef(rank=chunk.final_rank + 1,  # domain final_rank is 0-based; the public rank starts at 1
                  source=chunk.candidate.source, corpus=chunk.candidate.corpus,
                  subjects=chunk.candidate.subjects, last_updated=chunk.candidate.last_updated,
                  rerank_score=chunk.candidate.rerank_score)
        for chunk in sorted(r.selection.chunks, key=lambda c: c.final_rank)
    ]
    return AskRagResult(
        answer=WITHHELD_ANSWER if violation else r.answer,
        config=r.config,
        role=r.audience,
        status=status,
        planned_subjects=r.planned_subjects,
        cutoff=r.retrieval.cutoff,
        retrieval=RetrievalInfo(candidates_considered=len(r.retrieval.candidates)),
        sources=sources,
        security_audit=SecurityAuditView(
            violation=violation,
            violating_source_count=len(audit.violating_sources),
            explanation=SECURITY_VIOLATION_EXPLANATION if violation else None,
        ),
        judgement=None if violation else r.judgement,
    )


class HealthResult(_Frozen):
    """Readiness of the knowledge base, without any infrastructure identifier."""
    ready: bool
    collection_state: str  # control-plane status ("ACTIVE", "CREATING", ...) or "MISSING"
    index_present: bool | None
    chunk_count: int | None
    data_plane_reachable: bool | None  # None = not checked (collection missing or not ACTIVE)


def project_health(h: CollectionHealth) -> HealthResult:
    """An allow-list over manage.CollectionHealth: the endpoint and the data-plane
    error text stay with the operator's CLI."""
    active = h.status == "ACTIVE"
    return HealthResult(
        ready=active and h.index_exists is True and (h.chunk_count or 0) > 0,
        collection_state=h.status or "MISSING",
        index_present=h.index_exists,
        chunk_count=h.chunk_count,
        data_plane_reachable=(h.data_plane_error is None) if active else None,
    )


def _call(tool: str, use_case: Callable[[], T]) -> T:
    """Run a use case and translate its failure into this transport's terms.
    SystemExit is caught too: client.resolve_endpoint exits when the collection is
    missing or not ACTIVE, which must fail one call, not end the server. Known
    categories become a fixed ToolError — never the exception's message, which
    can name infrastructure. Anything else is re-raised for the SDK to report
    generically (traceback to the server's stderr only)."""
    try:
        return use_case()
    except (Exception, SystemExit) as exc:
        kind = classify_failure(exc)
        if kind == "internal":
            raise
        logger.warning("%s failed: %s (%s)", tool, kind, type(exc).__name__)
        raise ToolError(_TOOL_ERRORS[kind]) from None


class RoleCapability(_Frozen):
    configured: str
    supported: list[str]
    note: str


class ConfigurationCapability(_Frozen):
    name: ConfigName
    subject_filter: bool
    reranking: bool
    context_selection: Literal["all_retrieved", "fixed_count", "relevance_threshold"]
    summary: str


class JudgementCapability(_Frozen):
    parameter: Literal["judge"]
    default: bool
    judges: list[str]
    note: str


class SecurityCapability(_Frozen):
    access_filter: str
    security_audit: str


class OptionsCapability(_Frozen):
    question_max_chars: int
    updated_on_or_after: str


class Capabilities(_Frozen):
    """What this server can do — semantics, never infrastructure or tuning values."""
    contract_version: int
    role: RoleCapability
    configurations: list[ConfigurationCapability]
    default_configuration: ConfigName
    judgement: JudgementCapability
    security: SecurityCapability
    options: OptionsCapability
    subjects: list[str]
    subjects_resource: str


# What each configuration does, in words — deliberately without its pool sizes or
# thresholds, which are internal tuning that may change without a contract change.
_CONFIG_SEMANTICS: dict[ConfigName, tuple[bool, bool, str, str]] = {
    "baseline": (False, False, "all_retrieved",
                 "Vector search within the role's permitted content."),
    "filter-only": (True, False, "all_retrieved",
                    "Subject filter planned from the question (fails open), then vector search."),
    "rerank-only": (False, True, "fixed_count",
                    "Larger candidate pool, LLM reranking, a fixed number of top chunks kept."),
    "filter + rerank static": (True, True, "fixed_count",
                               "Subject filter, LLM reranking, a fixed number of top chunks kept."),
    "filter + rerank dynamic": (True, True, "relevance_threshold",
                                "Subject filter, LLM reranking, only chunks above a relevance threshold "
                                "kept; may return not_found."),
}


def build_capabilities(role: str) -> Capabilities:
    configurations = []
    for name in CONFIG_NAMES:
        subject_filter, reranking, selection, summary = _CONFIG_SEMANTICS[name]
        configurations.append(ConfigurationCapability(
            name=name, subject_filter=subject_filter, reranking=reranking,
            context_selection=selection, summary=summary,
        ))
    return Capabilities(
        contract_version=CAPABILITIES_CONTRACT_VERSION,
        role=RoleCapability(
            configured=role, supported=sorted(SUPPORTED_AUDIENCES),
            note="Server role fixed at startup; selects the audience filter. "
                 "Not authentication and not the identity of the MCP client.",
        ),
        configurations=configurations,
        default_configuration=DEFAULT_CONFIG,
        judgement=JudgementCapability(
            parameter="judge", default=False,
            judges=["faithfulness", "context_relevance", "context_completeness", "refusal"],
            note="Adds 3-4 model calls. context_completeness is skipped when no context is selected or "
                 "the answer is a refusal. Judgement is withheld when the security audit fails.",
        ),
        security=SecurityCapability(
            access_filter="Always applied from the configured role; unsupported roles are rejected "
                          "(fail closed).",
            security_audit="Every response includes security_audit. If retrieval returns content outside "
                           "the role's permitted audience, the answer, sources and judgement are withheld.",
        ),
        options=OptionsCapability(
            question_max_chars=MAX_QUESTION_CHARS,
            updated_on_or_after="Optional ISO date. Keeps documents updated on or after it. "
                                "Narrows retrieval; never widens access.",
        ),
        subjects=list(SUBJECTS),
        subjects_resource=SUBJECTS_URI,
    )


class LazyOpenSearchClient:
    """The OpenSearch client, created on first use rather than at startup, so the
    server starts (and capabilities/subjects answer) even while the collection
    is unreachable. Cached only after a successful creation — a failure such as
    client.resolve_endpoint's SystemExit is retried on the next call. Locked,
    because the SDK runs synchronous tools on worker threads."""

    def __init__(self):
        self._client = None
        self._lock = threading.Lock()

    def get(self):
        with self._lock:
            if self._client is None:
                self._client = client.opensearch_client()
            return self._client


def build_server(role: str) -> MCPServer:
    """The MCP server for one configured role. The role is validated first, so a
    server with an unsupported role is never constructed."""
    access_filter(role)  # the single source of truth for supported roles; raises UnsupportedAudienceError
    server = MCPServer(SERVER_NAME, version=SERVER_VERSION, log_level="INFO")
    opensearch = LazyOpenSearchClient()

    @server.tool()
    def ask_rag(question: Question, config: ConfigName = DEFAULT_CONFIG, judge: bool = False,
                updated_on_or_after: UpdatedOnOrAfter = None) -> AskRagResult:
        """Answer a question from the NovaOps knowledge base (employee handbook and, for the
        manager role, the manager playbook), as the role this server was started with.
        `config` picks the retrieval configuration; `judge` adds LLM quality scores (slower);
        `updated_on_or_after` keeps only documents updated on or after that date.
        A first call after an idle period can take a while as the knowledge base warms up."""
        result = _call("ask_rag", lambda: ask.ask(opensearch.get(), question, role, config,
                                                  judge=judge, cutoff=updated_on_or_after))
        return project_ask_result(result)

    @server.tool()
    def health_check() -> HealthResult:
        """Whether the knowledge base is ready to answer: collection state, index presence and
        chunk count. Read-only. An unhealthy collection is a normal result (ready=false); a
        call after an idle period also warms the knowledge base up."""
        return project_health(_call("health_check", lambda: manage.collection_health(manage.aoss_client())))

    @server.tool()
    def get_rag_capabilities() -> Capabilities:
        """What this NovaOps knowledge-base server can do: its configured role, the answer
        configurations and their behavior, the default, judging, security behavior,
        input options and the subject vocabulary."""
        return build_capabilities(role)

    @server.resource(SUBJECTS_URI, mime_type="application/json")
    def subjects() -> str:
        """The fixed subject vocabulary the planner and the subject filter use."""
        return _SUBJECTS_JSON

    return server


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="NovaOps knowledge base MCP server (STDIO or Streamable HTTP).")
    parser.add_argument("--role", required=True,
                        help=f"server role, one of {sorted(SUPPORTED_AUDIENCES)}; not authentication")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1",
                        help=f"streamable-http only; loopback only, one of {list(LOOPBACK_HOSTS)}")
    parser.add_argument("--port", type=int, default=8000, help="streamable-http only")
    args = parser.parse_args(argv)
    if args.host not in LOOPBACK_HOSTS:
        parser.error(f"--host must be a loopback address, one of {list(LOOPBACK_HOSTS)}: "
                     "the HTTP transport has no authentication")
    try:
        server = build_server(args.role)
    except UnsupportedAudienceError:
        parser.error(f"unsupported role {args.role!r}; expected one of {sorted(SUPPORTED_AUDIENCES)}")
    for name in NOISY_THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        if args.transport == "stdio":
            server.run("stdio")
        else:
            server.run("streamable-http", host=args.host, port=args.port, streamable_http_path=HTTP_PATH,
                       stateless_http=True, json_response=True)
    except KeyboardInterrupt:
        pass  # Ctrl+C on a manually started server: a normal stop, not an error


if __name__ == "__main__":
    main()
