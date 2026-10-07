"""The public, less-privileged views of the application's results — what may leave
the process through any transport adapter (the MCP server, the REST API).

A domain AskResult carries chunk text, vector scores and the sources a failed
security audit flagged; manage.CollectionHealth carries the collection endpoint
and raw data-plane error text. None of that may reach a caller, so adapters never
serialize those objects: they return the projections below. Keeping them in one
place means the withholding rules exist once, not once per transport.

Transport-independent on purpose: this module imports no MCP SDK and no web
framework, and knows nothing about tools, resources, routes or status codes.
"""
import logging
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from manage import CollectionHealth
from models import CONFIG_NAMES, AskResult, ConfigName, LiveJudgement

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 2000  # input / token-cost guard at the adapter boundary; not an ask() rule

# Fixed wording for a failed security audit: names the rule category only — never a
# file, a document or any of its text.
WITHHELD_ANSWER = ("The answer was withheld because a security check failed for this request. "
                   "Please report this to the system operator.")
SECURITY_VIOLATION_EXPLANATION = (
    "Access-control audit failed: retrieval returned content outside the audience permitted "
    "for the configured role. The answer, sources and judgement were withheld.")

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_CHARS)]


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
    """The less-privileged public view of an AskResult: no chunk text, no vector
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
        logger.warning("security audit failed: answer withheld, violating source count=%d",
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


class ConfigurationCapability(_Frozen):
    name: ConfigName
    subject_filter: bool
    reranking: bool
    context_selection: Literal["all_retrieved", "fixed_count", "relevance_threshold"]
    summary: str


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


def configuration_capabilities() -> list[ConfigurationCapability]:
    """Every configuration, in CONFIG_NAMES order, described by behavior only."""
    configurations = []
    for name in CONFIG_NAMES:
        subject_filter, reranking, selection, summary = _CONFIG_SEMANTICS[name]
        configurations.append(ConfigurationCapability(
            name=name, subject_filter=subject_filter, reranking=reranking,
            context_selection=selection, summary=summary,
        ))
    return configurations
