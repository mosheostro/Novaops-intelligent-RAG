"""Evaluate the filter + rerank mix against a plain vector baseline.

Runs the shared question set (data/eval_questions.jsonl) through FIVE
configurations and scores each answer with the judges in judges.py:

    1. baseline                 access filter only, vector top-4, no rerank
    2. filter-only               + subject planner filter, vector top-4, no rerank
    3. rerank-only               access filter only, pool N=10, rerank, static top-3
    4. filter + rerank static    + subject filter, pool N=10, rerank, static top-3
    5. filter + rerank dynamic   + subject filter, pool N=10, rerank, keep score >= 0.6

The access filter (retrieval.access_filter, via knn_search's `audience` arg) is
ON in every configuration — it is never the thing being measured. The subject
filter and reranking are the two levers under test, isolated and combined:

    1 -> 2   isolates the subject filter (top_k held at 4 in both)
    1 -> 3   isolates reranking (together with the top_k 4 -> 3 shrink)
    3 -> 4   the subject filter on top of reranking
    2 -> 4   reranking on top of the subject filter
    4 -> 5   the static vs. dynamic cut, over the SAME ranked pool

`evaluate()` performs all computation and returns an `EvaluationResult` — a
frozen Pydantic domain object (see models.py and
docs/evaluation-domain-model.md for the full contract and its rationale).
`report()` is a thin presentation layer over that object; nothing a future UI
needs lives only in printed text. This module is functional throughout: no
`EvaluationEngine`, no config objects, just functions building and returning
typed domain objects instead of dicts.

Two call-sharing rules keep this affordable and keep static vs. dynamic a fair
comparison:

  - `plan_subjects(question)` runs ONCE per question and is reused by every
    config that applies a subject filter (filter-only, and both filter+rerank
    configs). baseline and rerank-only never see it.
  - Reranking runs ONCE per (question, audience, subjects) retrieval condition.
    rerank-only's pool (no subject filter) and the filter+rerank pool (subject
    filter applied) are two DIFFERENT conditions and are each reranked once;
    the filter+rerank pool's single ranked result is then cut two different
    ways (static and dynamic) — sharing the SAME RetrievalResult object for
    both, so those two rows differ only in the cut, never in reranker noise or
    in a re-run security audit.

No exception from plan_subjects, knn_search, rerank_all, or answer is caught
here — a Bedrock/OpenSearch/network failure is a technical failure and must
propagate, not be mistaken for a valid empty plan, an empty context, or a fake
score. The one intentional empty result is the dynamic cut when no candidate
clears the threshold: SelectionResult.status becomes "not_found" with zero
chunks, while context_texts stays the literal ["not found"] retrieval.answer()
needs for its existing "say so plainly" behavior — nothing here special-cases
the answer step further.

    python eval.py
"""
import json
from pathlib import Path

from client import opensearch_client
from judges import completeness, context_relevance, faithfulness, refused
from models import (
    CONFIG_NAMES,
    Candidate,
    ConfigName,
    ConfigSummary,
    ConfigurationResult,
    ContentEvaluation,
    Evaluation,
    EvaluationMetadata,
    EvaluationResult,
    QuestionResult,
    RefusalEvaluation,
    RetrievalResult,
    SecurityAudit,
    SelectedChunk,
    SelectionResult,
)
from planner import plan_subjects
from reranker import rerank_all
from retrieval import answer, knn_search

BASELINE_TOP_K = 4        # baseline / filter-only: plain vector context size
CANDIDATE_POOL_SIZE = 10  # rerank configs: candidates retrieved BEFORE reranking
RERANK_STATIC_TOP_K = 3   # rerank configs: fixed-count cut after reranking
MIN_RERANK_SCORE = 0.6    # dynamic cut: keep every candidate at or above this

MAX_REPORT_ANSWER_CHARS = 600  # presentation only -- ConfigurationResult.answer is never shortened

QUESTIONS_FILE = Path(__file__).resolve().parent / "data" / "eval_questions.jsonl"


def load_questions() -> list[dict]:
    """Question records straight from the JSONL, one dict per line — including
    an optional "report" boolean (default false), which flags a question for
    the detailed per-config report in report(). "report" is presentation
    metadata only: it never reaches evaluate()/evaluate_question(), which read
    only the fields they always have (id, question, audience, expect_refusal,
    key_facts) and simply ignore any extra key a record happens to carry."""
    return [json.loads(line) for line in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


# --- candidates: OpenSearch hits -> domain objects -------------------------------

def hits_to_candidates(hits: list[dict]) -> list[Candidate]:
    """Convert raw OpenSearch hits (already in vector-search order, most
    relevant first) into Candidate domain objects carrying content AND
    metadata.

    `vector_rank` is 0-based: index 0 is the hit closest by cosine/inner-product
    score, matching the position of that hit in `hits`. `rerank_score` starts
    as None; attach_rerank_scores() below fills it in for reranked pools only."""
    return [
        Candidate(
            text=h["_source"]["text"],
            source=h["_source"]["source"],
            corpus=h["_source"]["corpus"],
            audience=h["_source"]["audience"],
            subjects=h["_source"]["subjects"],
            last_updated=h["_source"]["last_updated"],
            vector_score=h["_score"],
            vector_rank=i,
        )
        for i, h in enumerate(hits)
    ]


def rerank_candidates(query: str, candidates: list[Candidate]) -> list[tuple[Candidate, float]]:
    """Adapter around the UNTOUCHED reranker.rerank_all(), whose dict-in/dict-
    out contract is fixed (reranker.py is not modified by this design). Reading
    reranker.py shows it only ever reads a candidate's "text", so the
    projection here is a single field, not a full dict conversion. rerank_all
    returns the SAME dict objects it was given (reordered, never copied), so
    matching its output back to the original Candidate objects by identity of
    the small dict wrapper is exact. This is the one, narrow place a domain
    object is briefly represented as a dict — not a general reversion to
    dicts, and not the "dict -> JSON -> Pydantic" pattern the domain model
    design explicitly rejects (see docs/evaluation-domain-model.md §8, §10)."""
    as_dicts = [{"text": c.text} for c in candidates]
    ranked_dicts = rerank_all(query, as_dicts)  # list[(dict, score)], best first
    candidate_by_dict_id = {id(d): c for d, c in zip(as_dicts, candidates)}
    return [(candidate_by_dict_id[id(d)], score) for d, score in ranked_dicts]


def attach_rerank_scores(
    pool: list[Candidate], ranked: list[tuple[Candidate, float]]
) -> tuple[list[Candidate], list[tuple[Candidate, float]]]:
    """Pure transformation — Candidate is frozen, so this REBUILDS rather than
    mutates. `pool` is in its original vector-retrieval order; `ranked` is
    rerank_candidates()'s best-first (candidate, score) pairs, still pointing
    at the ORIGINAL `pool` objects. Returns:
      - the pool, same vector order, each candidate's rerank_score now set;
      - the ranked list, same best-first order, pointing at those SAME updated
        instances — so RetrievalResult.candidates and every
        SelectedChunk.candidate built from `ranked` refer to identical
        objects, never two different copies of "the same" candidate."""
    score_by_id = {id(c): score for c, score in ranked}
    # .get(..., None): a candidate absent from `ranked` (e.g. an omitted-by-the-
    # model edge case) gets rerank_score=None rather than raising -- the same
    # defensive default the original annotate_rerank_scores() used.
    updated_pool = [c.model_copy(update={"rerank_score": score_by_id.get(id(c))}) for c in pool]
    updated_by_old_id = {id(old): new for old, new in zip(pool, updated_pool)}
    updated_ranked = [(updated_by_old_id[id(c)], score) for c, score in ranked]
    return updated_pool, updated_ranked


# --- selection: pure, no model/network calls, no knowledge of SelectionResult ---

def select_context(
    ranked: list[tuple[Candidate, float]], mode: str,
    static_k: int = RERANK_STATIC_TOP_K, min_score: float = MIN_RERANK_SCORE,
) -> list[tuple[Candidate, float]]:
    """Cut an already-ranked (best-first) pool. Pure — no I/O, no knowledge of
    SelectionResult or the "not found" sentinel (that's build_selection_result,
    below); just the cut itself, so it stays trivially unit-testable.

      - "static":  keep the first `static_k`.
      - "dynamic": keep every candidate scoring >= `min_score`.

    Dynamic never falls back to the top-1: if nothing clears the bar, the
    result is simply empty — a deliberate reliability choice, not a bug. Low-
    confidence retrieval must read as "no evidence", never as apparently-valid
    evidence."""
    if mode == "static":
        return list(ranked[:static_k])
    if mode == "dynamic":
        return [pair for pair in ranked if pair[1] >= min_score]
    raise ValueError(f"unknown context-selection mode: {mode!r}")


def build_selection_result(selected: list[tuple[Candidate, float]]) -> SelectionResult:
    """Turn a cut — from select_context(), or "everything" for baseline/
    filter-only via _select_all() below — into a SelectionResult.

    status is "not_found" if and only if `selected` is empty; even then,
    context_texts is the literal ["not found"] retrieval.answer() needs to
    produce its existing grounded-refusal behavior — never derived from an
    empty chunk list, and never a top-1 fallback."""
    if not selected:
        return SelectionResult(status="not_found", chunks=[], context_texts=["not found"])
    chunks = [SelectedChunk(candidate=c, final_rank=i) for i, (c, _score) in enumerate(selected)]
    context_texts = [c.text for c, _score in selected]
    return SelectionResult(status="selected", chunks=chunks, context_texts=context_texts)


def _select_all(pool: list[Candidate]) -> SelectionResult:
    """Baseline/filter-only: no cut is applied — every retrieved candidate is
    used, in retrieval order (final_rank ends up equal to vector_rank, since
    `pool` is already in that order and build_selection_result numbers by
    position). Deliberately NOT routed through select_context()'s static/
    dynamic modes: there is no relevance-ranked list to cut here, and adding a
    third "keep everything" mode — or inventing a fake rerank score just to
    reuse that code path — would manufacture a selection concept that doesn't
    reflect a real domain difference (see docs/evaluation-domain-model.md §10's
    judgment call: this is a case where unifying would be cosmetic, not
    architectural). What IS shared with the rerank configs is the actual
    SelectionResult construction, via build_selection_result — the one place
    that logic lives, for all five configs."""
    return build_selection_result([(c, c.vector_score) for c in pool])


# --- security: audit only, never "fixes" anything -------------------------------

def audit_security(candidates: list[Candidate], role: str) -> SecurityAudit:
    """Did retrieval, for this (question, config), actually return a chunk this
    role must never see? An employee may only see audience == "all"; a manager
    may see anything the corpus has. This is an AUDIT of what knn_search
    returned — retrieval.access_filter is the enforcement; this only records
    whether it held, for every candidate the pool returned (not just the ones
    that made the final context). A violation here is reported, never
    silently corrected."""
    if role != "employee":
        return SecurityAudit(violation=False, violating_sources=[])
    bad_sources = [c.source for c in candidates if c.audience == "manager"]
    return SecurityAudit(violation=bool(bad_sources), violating_sources=bad_sources)


# --- judges: content metrics vs. the refusal check ------------------------------

def score_answer(q: dict, contexts: list[str], answer_text: str) -> Evaluation:
    """Refusal questions are scored ONLY by refused() — the content judges are
    not run on them (there is no expected content to be faithful to, relevant
    to, or complete against). Every other question gets all three judges. Judge
    scores are preserved exactly as returned; each judge's one-sentence reason
    is kept alongside it so a future UI has it without re-running anything."""
    if q["expect_refusal"]:
        return RefusalEvaluation(refusal_ok=refused(answer_text))
    f_score, f_reason = faithfulness(q["question"], contexts, answer_text)
    r_score, r_reason = context_relevance(q["question"], contexts)
    c_score, c_reason = completeness(q["question"], q["key_facts"], answer_text)
    return ContentEvaluation(
        faithfulness=f_score, faithfulness_reason=f_reason,
        context_relevance=r_score, context_relevance_reason=r_reason,
        completeness=c_score, completeness_reason=c_reason,
    )


def run_config(
    name: ConfigName, q: dict, retrieval: RetrievalResult, selection: SelectionResult,
) -> ConfigurationResult:
    """Generate the grounded answer for one config's selection, score it, and
    package the result. Computation only — no printing. This is the per-config
    leaf of evaluate()'s structured result."""
    answer_text = answer(q["question"], selection.context_texts)
    evaluation = score_answer(q, selection.context_texts, answer_text)
    return ConfigurationResult(
        name=name, retrieval=retrieval, selection=selection, answer=answer_text, evaluation=evaluation,
    )


def build_retrieval_result(
    role: str, subjects_applied: list[str] | None, top_k_requested: int, pool: list[Candidate],
) -> RetrievalResult:
    """Assemble the retrieval side of one configuration: the filters that were
    actually applied, the raw pool, and a security audit over that WHOLE pool."""
    security = audit_security(pool, role)
    return RetrievalResult(
        audience=role, subjects_applied=subjects_applied, top_k_requested=top_k_requested,
        candidates=pool, security=security,
    )


def evaluate_question(client, q: dict) -> QuestionResult:
    """Run one question through all five configs. plan_subjects runs exactly
    once here; the reranker runs exactly twice (once for the rerank-only pool,
    once — shared — for the filter+rerank pool, whose single RetrievalResult is
    then reused, by reference, for both the static and dynamic configs)."""
    role, question = q["audience"], q["question"]
    planned_subjects = plan_subjects(question)  # ONE call, reused below

    configs: dict[ConfigName, ConfigurationResult] = {}

    # 1. baseline — no subject filter, vector top-4, no rerank.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=None, top_k=BASELINE_TOP_K))
    retrieval = build_retrieval_result(role, None, BASELINE_TOP_K, pool)
    configs["baseline"] = run_config("baseline", q, retrieval, _select_all(pool))

    # 2. filter-only — subject filter (reused plan), vector top-4, no rerank.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=planned_subjects, top_k=BASELINE_TOP_K))
    retrieval = build_retrieval_result(role, planned_subjects, BASELINE_TOP_K, pool)
    configs["filter-only"] = run_config("filter-only", q, retrieval, _select_all(pool))

    # 3. rerank-only — its OWN pool (no subject filter), N=10, rerank ONCE, static cut.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=None, top_k=CANDIDATE_POOL_SIZE))
    pool, ranked = attach_rerank_scores(pool, rerank_candidates(question, pool))  # ONE rerank call
    retrieval = build_retrieval_result(role, None, CANDIDATE_POOL_SIZE, pool)
    configs["rerank-only"] = run_config(
        "rerank-only", q, retrieval, build_selection_result(select_context(ranked, "static")),
    )

    # 4 & 5. filter + rerank — ONE shared pool + ONE rerank call, cut two ways.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=planned_subjects, top_k=CANDIDATE_POOL_SIZE))
    pool, ranked = attach_rerank_scores(pool, rerank_candidates(question, pool))  # ONE call, shared
    retrieval = build_retrieval_result(role, planned_subjects, CANDIDATE_POOL_SIZE, pool)  # shared by reference below

    configs["filter + rerank static"] = run_config(
        "filter + rerank static", q, retrieval, build_selection_result(select_context(ranked, "static")),
    )
    configs["filter + rerank dynamic"] = run_config(
        "filter + rerank dynamic", q, retrieval, build_selection_result(select_context(ranked, "dynamic")),
    )

    return QuestionResult(
        id=q["id"], question=question, audience=role, expect_refusal=q["expect_refusal"],
        key_facts=q["key_facts"], planned_subjects=planned_subjects, configurations=configs,
    )


def mean(xs: list[float]) -> float | None:
    """Average of `xs`, or None if empty. None (not NaN) is used deliberately:
    it round-trips through JSON as null, and this structure is meant to be
    consumed directly, not just printed."""
    return sum(xs) / len(xs) if xs else None


def summarize(per_question: dict[str, QuestionResult]) -> dict[ConfigName, ConfigSummary]:
    """Aggregate per-config averages across every question. Refusal questions
    contribute to refusal_ok only; content-judge lists only ever contain
    scores from non-refusal questions, so an all-refusal question set would
    correctly report those averages as None rather than a misleading 0.0.
    n_chunks reads ConfigurationResult.n_chunks — the computed property — so a
    "not_found" dynamic result correctly contributes 0, not len(["not found"])."""
    summary: dict[ConfigName, ConfigSummary] = {}
    for name in CONFIG_NAMES:
        n_chunks, faith, ctx_rel, complete, refusal_ok = [], [], [], [], []
        violations = 0
        for q_result in per_question.values():
            cfg = q_result.configurations[name]
            n_chunks.append(cfg.n_chunks)
            if isinstance(cfg.evaluation, RefusalEvaluation):
                refusal_ok.append(1.0 if cfg.evaluation.refusal_ok else 0.0)
            else:
                faith.append(cfg.evaluation.faithfulness)
                ctx_rel.append(cfg.evaluation.context_relevance)
                complete.append(cfg.evaluation.completeness)
            if cfg.retrieval.security.violation:
                violations += 1
        summary[name] = ConfigSummary(
            n_chunks_avg=mean(n_chunks),
            faithfulness_avg=mean(faith),
            context_relevance_avg=mean(ctx_rel),
            completeness_avg=mean(complete),
            refusal_ok_avg=mean(refusal_ok),
            security_violations=violations,
        )
    return summary


def evaluate(client, questions: list[dict]) -> EvaluationResult:
    """Run every question through all five configs and return ONE
    EvaluationResult — a frozen domain object, not a dict, and no printing. A
    future UI renders directly from this; report() below is just one consumer
    of it (the CLI table). See models.py / docs/evaluation-domain-model.md for
    the full shape and its rationale."""
    per_question = {q["id"]: evaluate_question(client, q) for q in questions}
    metadata = EvaluationMetadata(
        question_count=len(questions),
        configs=list(CONFIG_NAMES),
        candidate_pool_size=CANDIDATE_POOL_SIZE,
        static_top_k=RERANK_STATIC_TOP_K,
        dynamic_threshold=MIN_RERANK_SCORE,
        baseline_top_k=BASELINE_TOP_K,
    )
    return EvaluationResult(metadata=metadata, questions=per_question, summary=summarize(per_question))


def _fmt(x: float | None, spec: str = ".2f") -> str:
    return "  n/a" if x is None else format(x, spec)


def truncate_answer(answer_text: str, max_chars: int = MAX_REPORT_ANSWER_CHARS) -> str:
    """CLI presentation only — never applied to ConfigurationResult.answer
    itself, which always holds the complete, untruncated text. A simple
    character cut, not token-aware: this is a diagnostic preview, not a
    length a model call has to respect."""
    if len(answer_text) <= max_chars:
        return answer_text
    return answer_text[:max_chars] + "\n...\n[truncated]"


def _selected_question_ids(questions: list[dict]) -> list[str]:
    """Which question ids are flagged for the detailed report. The JSONL's
    "report" field is the only source of truth — nothing here is hard-coded,
    and a record with no "report" key at all defaults to not selected."""
    return [q["id"] for q in questions if q.get("report", False)]


def _print_configuration_detail(cfg: ConfigurationResult) -> None:
    print("-" * 62)
    print(cfg.name)
    print("-" * 62)
    print("Answer:")
    print(truncate_answer(cfg.answer))
    print(f"\nSelection status: {cfg.selection.status}")
    print(f"Selected chunks: {cfg.n_chunks}")
    if cfg.selection.chunks:
        print("Sources:")
        for sc in cfg.selection.chunks:
            score_part = (f"  rerank_score={sc.candidate.rerank_score:.2f}"
                          if sc.candidate.rerank_score is not None else "")
            print(f"  [{sc.final_rank}] {sc.candidate.source}{score_part}")
    print("Judge:")
    if isinstance(cfg.evaluation, RefusalEvaluation):
        print(f"  refusal_ok={cfg.evaluation.refusal_ok}")
    else:
        print(f"  faithfulness={cfg.evaluation.faithfulness:.2f}  "
              f"context_relevance={cfg.evaluation.context_relevance:.2f}  "
              f"completeness={cfg.evaluation.completeness:.2f}")
    print()


def _print_question_detail(q_result: QuestionResult) -> None:
    print(f"\nQUESTION: {q_result.id}")
    print(f"AUDIENCE: {q_result.audience}")
    print(f"EXPECTED REFUSAL: {q_result.expect_refusal}")
    print(f"Question text: {q_result.question}\n")
    for name in CONFIG_NAMES:
        cfg = q_result.configurations[name]
        _print_configuration_detail(cfg)


def _print_selected_report(results: EvaluationResult, questions: list[dict]) -> None:
    """The SAME question, shown across all five configurations, for every
    question flagged report=true in the input. This never re-runs evaluation —
    it only reads the already-computed EvaluationResult."""
    selected_ids = _selected_question_ids(questions)
    if not selected_ids:
        return
    print("\n" + "=" * 78)
    print("SELECTED EVALUATION REPORT")
    print("=" * 78)
    for qid in selected_ids:
        _print_question_detail(results.questions[qid])


def report(results: EvaluationResult, questions: list[dict] | None = None) -> None:
    """Presentation layer only — every number here also lives in `results`.

    The existing summary table is unchanged. When `questions` is given (the
    same list passed to evaluate()), a second, detailed section follows,
    showing every question flagged report=true across all five configs — for
    comparing how one question's answer changes by configuration. Omitting
    `questions` (or passing none flagged) reproduces the exact prior output."""
    meta = results.metadata
    print("\n" + "=" * 78)
    print("FILTER + RERANK MIX — measured effect (averages over the question set)")
    print("=" * 78)
    print(f"candidate pool N={meta.candidate_pool_size}  static top-k={meta.static_top_k}  "
          f"dynamic threshold={meta.dynamic_threshold}  baseline top-k={meta.baseline_top_k}")
    header = f"{'config':26} {'chunks':>7} {'faithful':>9} {'ctx_rel':>9} {'complete':>9} {'refuse_ok':>10} {'sec_viol':>9}"
    print(header)
    print("-" * len(header))
    for name in CONFIG_NAMES:
        s = results.summary[name]
        print(f"{name:26} {_fmt(s.n_chunks_avg, '.1f'):>7} {_fmt(s.faithfulness_avg):>9} "
              f"{_fmt(s.context_relevance_avg):>9} {_fmt(s.completeness_avg):>9} "
              f"{_fmt(s.refusal_ok_avg):>10} {s.security_violations:>9}")
    print("\n'chunks' is the AVERAGE final context size each config fed the model — fixed at 4 for")
    print("baseline/filter-only and 3 for the static rerank configs, but VARIABLE for the dynamic")
    print("cut (candidate POOL size is fixed at N; final context size is what varies). 'sec_viol'")
    print("counts questions where an employee's retrieval returned a manager-only chunk — this")
    print("must read 0 for every config; a nonzero value is a retrieval bug, not a quality result.")

    if questions:
        _print_selected_report(results, questions)


def main() -> None:
    client = opensearch_client()
    questions = load_questions()
    print(f"Evaluating {len(questions)} questions x {len(CONFIG_NAMES)} configs "
          "— this makes a lot of model calls (a few minutes).")
    report(evaluate(client, questions), questions)


if __name__ == "__main__":
    main()
