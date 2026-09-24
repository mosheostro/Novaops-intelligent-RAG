"""Domain models for the evaluation result — see docs/evaluation-domain-model.md.

Pydantic is the in-process domain-contract layer between eval.py's computation
and every consumer: the current CLI report, and eventually a dashboard, an API,
or an MCP tool layer. These models are used for their structure and validation
INSIDE Python; JSON only appears at an external boundary (a future API/MCP
response, a saved artifact) via `.model_dump()` / `.model_dump_json()`. There is
no dict-building stage before these models exist, and none after, before
something external actually needs JSON.

Every model is frozen: an EvaluationResult (and everything nested inside it) is
a finished, historical snapshot of one evaluation run — not a live, mutable
view that could drift after the run completed.

This module holds no logic beyond field validation; it does not know how a
question is evaluated, retrieved, reranked, or scored. That stays in eval.py,
which imports these types and constructs them.
"""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# The five configurations are a closed set — a Literal, not an Enum, so no new
# class machinery is needed just to get validation and dict-key typing.
ConfigName = Literal[
    "baseline",
    "filter-only",
    "rerank-only",
    "filter + rerank static",
    "filter + rerank dynamic",
]

CONFIG_NAMES: tuple[ConfigName, ...] = (
    "baseline",
    "filter-only",
    "rerank-only",
    "filter + rerank static",
    "filter + rerank dynamic",
)


class _Frozen(BaseModel):
    """Base for every domain model below: immutable once constructed."""
    model_config = ConfigDict(frozen=True)


class Candidate(_Frozen):
    """A chunk as retrieval — and, for reranked pools, reranking — returned it,
    before any selection decision has been made.

    `vector_rank` is 0-based: index 0 is the hit closest by cosine/inner-
    product score, matching its position in the k-NN hit list. `rerank_score`
    is None for pools that are never reranked (baseline, filter-only) and,
    transiently while a reranked pool is being built, before scores are known."""
    text: str
    source: str
    corpus: str
    audience: str
    subjects: list[str]
    last_updated: str
    vector_score: float
    vector_rank: int
    rerank_score: float | None = None


class SelectedChunk(_Frozen):
    """A Candidate that a selection policy chose, and where it landed.

    Exists only after selection — a bare Candidate never carries a final_rank,
    and a SelectedChunk always does. Static and dynamic selection over the same
    ranked pool produce different SelectedChunks (different final_rank, and
    possibly a different subset), never a final_rank mutated onto a shared
    Candidate."""
    candidate: Candidate
    final_rank: int


class SecurityAudit(_Frozen):
    """Whether this retrieval, for this question and role, returned anything it
    should not have.

    An audit of the FULL retrieved pool, never just the selected chunks — a
    leak into the pool is a security fact regardless of whether that chunk was
    later selected for the answer. A hard invariant, never a quality score:
    violations are reported here, never corrected."""
    violation: bool
    violating_sources: list[str]


class RetrievalResult(_Frozen):
    """What came back from OpenSearch for one configuration, and whether it was
    safe.

    `subjects_applied` is None when no subject filter was used at all
    (baseline, rerank-only) — distinct from an empty list, which means the
    planner ran and deliberately found nothing to filter on (fail-open)."""
    audience: str
    subjects_applied: list[str] | None
    top_k_requested: int
    candidates: list[Candidate]
    security: SecurityAudit


class SelectionResult(_Frozen):
    """What was chosen from a RetrievalResult, and what was actually sent to
    retrieval.answer().

    `status == "not_found"` if and only if `chunks == []`. Even then,
    `context_texts` is still the literal `["not found"]` — the presentation
    string retrieval.answer() needs, unchanged, to produce its existing
    grounded-refusal behavior. Domain truth (`chunks`) and prompt presentation
    (`context_texts`) are deliberately two different fields: counting chunks
    means `len(chunks)`, never `len(context_texts)`."""
    status: Literal["selected", "not_found"]
    chunks: list[SelectedChunk]
    context_texts: list[str]


class ContentEvaluation(_Frozen):
    """Judge scores for an ordinary, answerable question."""
    kind: Literal["content"] = "content"
    faithfulness: float
    faithfulness_reason: str
    context_relevance: float
    context_relevance_reason: str
    completeness: float
    completeness_reason: str


class RefusalEvaluation(_Frozen):
    """The refusal check for a question expected to be refused.

    No content judges run for these — there is no expected content to be
    faithful to, relevant to, or complete against."""
    kind: Literal["refusal"] = "refusal"
    refusal_ok: bool


# Which variant a ConfigurationResult gets is fully determined by the
# question's expect_refusal flag, never mixed within one question's configs.
Evaluation = Annotated[Union[ContentEvaluation, RefusalEvaluation], Field(discriminator="kind")]


class ConfigurationResult(_Frozen):
    """Everything produced for one (question, config) pair — the main object a
    future UI renders, and self-describing on its own (`name`) even though it
    also sits under a ConfigName-keyed dict on QuestionResult."""
    name: ConfigName
    retrieval: RetrievalResult
    selection: SelectionResult
    answer: str
    evaluation: Evaluation

    @property
    def n_chunks(self) -> int:
        """Read-only, never stored: the number of chunks actually selected —
        correctly 0 for a not_found selection, unlike len(context_texts)."""
        return len(self.selection.chunks)


class QuestionResult(_Frozen):
    """Everything produced for one question, across all five configurations."""
    id: str
    question: str
    audience: str
    expect_refusal: bool
    key_facts: list[str]
    planned_subjects: list[str]
    configurations: dict[ConfigName, ConfigurationResult]


class EvaluationMetadata(_Frozen):
    """Run-level constants, recorded alongside the results they produced."""
    question_count: int
    configs: list[ConfigName]
    candidate_pool_size: int
    static_top_k: int
    dynamic_threshold: float
    baseline_top_k: int


class ConfigSummary(_Frozen):
    """Aggregate averages for one configuration, across every question. Any
    average is None (never a misleading 0.0) when its underlying list of
    scores is empty — see eval.py's mean()."""
    n_chunks_avg: float | None
    faithfulness_avg: float | None
    context_relevance_avg: float | None
    completeness_avg: float | None
    refusal_ok_avg: float | None
    security_violations: int


class EvaluationResult(_Frozen):
    """The top-level contract: what evaluate() returns, and what every
    consumer — the CLI report, and eventually a dashboard/API/MCP layer —
    holds. A finished, self-describing snapshot of one evaluation run.

    `summary` is computed once by eval.py's summarize() and stored here, not a
    lazily recomputed property — an EvaluationResult is a historical record,
    not a live view that should re-derive its own averages on every read."""
    metadata: EvaluationMetadata
    questions: dict[str, QuestionResult]
    summary: dict[ConfigName, ConfigSummary]
