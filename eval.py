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

`evaluate()` performs all computation and returns a plain, structured,
JSON-shaped result — see its docstring for the exact shape. `report()` is a
thin presentation layer over that structure; nothing a future UI needs lives
only in printed text. This module is functional throughout: no
`EvaluationEngine`, no config objects, just functions passing plain dicts.

Two call-sharing rules keep this affordable and keep static vs. dynamic a fair
comparison:

  - `plan_subjects(question)` runs ONCE per question and is reused by every
    config that applies a subject filter (filter-only, and both filter+rerank
    configs). baseline and rerank-only never see it.
  - `rerank_all(query, candidates)` runs ONCE per (question, audience, subjects)
    retrieval condition. rerank-only's pool (no subject filter) and the
    filter+rerank pool (subject filter applied) are two DIFFERENT conditions
    and are each reranked once; the filter+rerank pool's single ranked result
    is then cut two different ways (static and dynamic), so those two rows
    differ only in the cut, never in reranker noise.

No exception from plan_subjects, knn_search, rerank_all, or answer is caught
here — a Bedrock/OpenSearch/network failure is a technical failure and must
propagate, not be mistaken for a valid empty plan, an empty context, or a fake
score. The one intentional empty result is the dynamic cut when no candidate
clears the threshold: that becomes the literal context ["not found"], handled
entirely by retrieval.answer()'s existing "say so plainly" behavior — nothing
here special-cases it further.

    python eval.py
"""
import json
from pathlib import Path

from client import opensearch_client
from judges import completeness, context_relevance, faithfulness, refused
from planner import plan_subjects
from reranker import rerank_all
from retrieval import answer, knn_search

BASELINE_TOP_K = 4        # baseline / filter-only: plain vector context size
CANDIDATE_POOL_SIZE = 10  # rerank configs: candidates retrieved BEFORE reranking
RERANK_STATIC_TOP_K = 3   # rerank configs: fixed-count cut after reranking
MIN_RERANK_SCORE = 0.6    # dynamic cut: keep every candidate at or above this

CONFIG_NAMES = [
    "baseline",
    "filter-only",
    "rerank-only",
    "filter + rerank static",
    "filter + rerank dynamic",
]

QUESTIONS_FILE = Path(__file__).resolve().parent / "data" / "eval_questions.jsonl"


def load_questions() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


# --- candidates: OpenSearch hits -> plain, metadata-preserving dicts ------------

def hits_to_candidates(hits: list[dict]) -> list[dict]:
    """Convert raw OpenSearch hits (already in vector-search order, most
    relevant first) into candidate dicts carrying content AND metadata.

    `vector_rank` is 0-based: index 0 is the hit closest by cosine/inner-product
    score, matching the position of that hit in `hits`. `rerank_score` starts
    as None; annotate_rerank_scores() fills it in for reranked pools only."""
    return [
        {
            "text": h["_source"]["text"],
            "source": h["_source"]["source"],
            "corpus": h["_source"]["corpus"],
            "audience": h["_source"]["audience"],
            "subjects": h["_source"]["subjects"],
            "last_updated": h["_source"]["last_updated"],
            "vector_score": h["_score"],
            "vector_rank": i,
            "rerank_score": None,
        }
        for i, h in enumerate(hits)
    ]


def annotate_rerank_scores(candidates: list[dict], ranked: list[tuple[dict, float]]) -> None:
    """Attach each candidate's reranker score IN PLACE on the shared pool, keyed
    by object identity (rerank_all reorders references, it never copies). Safe
    to call once per pool: the score is a property of (pool, query), not of any
    one cut, so static and dynamic read the same annotated pool."""
    score_by_id = {id(c): s for c, s in ranked}
    for c in candidates:
        c["rerank_score"] = score_by_id.get(id(c))


# --- context selection: pure, no model/network calls ----------------------------

def select_context(
    ranked: list[tuple[dict, float]], mode: str,
    static_k: int = RERANK_STATIC_TOP_K, min_score: float = MIN_RERANK_SCORE,
) -> tuple[list[tuple[dict, float]], list[str]]:
    """Cut an already-ranked (best-first) pool. Pure — no I/O, easy to test.

      - "static":  keep the first `static_k`.
      - "dynamic": keep every candidate scoring >= `min_score`.

    Dynamic never falls back to the top-1: if nothing clears the bar, the
    selection is empty and the context is the literal ["not found"] — a
    deliberate reliability choice, not a bug. Low-confidence retrieval must
    read as "no evidence", never as apparently-valid evidence."""
    if mode == "static":
        selected = list(ranked[:static_k])
    elif mode == "dynamic":
        selected = [pair for pair in ranked if pair[1] >= min_score]
    else:
        raise ValueError(f"unknown context-selection mode: {mode!r}")
    if not selected:
        return [], ["not found"]
    return selected, [c["text"] for c, _ in selected]


def _rank_selected(selected: list[tuple[dict, float]]) -> list[dict]:
    """Selected (candidate, score) pairs -> candidate dicts, each copied (never
    mutating the shared pool) and stamped with its 0-based `final_rank` in THIS
    cut. Needed because the same pool's dicts are shared between the static and
    dynamic cuts; final_rank differs per cut and must not leak between them."""
    return [{**c, "final_rank": rank} for rank, (c, _score) in enumerate(selected)]


# --- security: audit only, never "fixes" anything -------------------------------

def audience_violation(candidates: list[dict], role: str) -> tuple[bool, list[str]]:
    """Did retrieval, for this (question, config), actually return a chunk this
    role must never see? An employee may only see audience == "all"; a manager
    may see anything the corpus has. This is an AUDIT of what knn_search
    returned — retrieval.access_filter is the enforcement; this only records
    whether it held, for every candidate the pool returned (not just the ones
    that made the final context). A violation here is reported, never
    silently corrected."""
    if role != "employee":
        return False, []
    bad_sources = [c["source"] for c in candidates if c.get("audience") == "manager"]
    return bool(bad_sources), bad_sources


# --- judges: content metrics vs. the refusal check ------------------------------

def score_answer(q: dict, contexts: list[str], answer_text: str) -> dict:
    """Refusal questions are scored ONLY by refused() — the content judges are
    not run on them (there is no expected content to be faithful to, relevant
    to, or complete against). Every other question gets all three judges. Judge
    scores are preserved exactly as returned; each judge's one-sentence reason
    is kept alongside it so a future UI has it without re-running anything."""
    if q["expect_refusal"]:
        return {"refusal_ok": refused(answer_text)}
    f_score, f_reason = faithfulness(q["question"], contexts, answer_text)
    r_score, r_reason = context_relevance(q["question"], contexts)
    c_score, c_reason = completeness(q["question"], q["key_facts"], answer_text)
    return {
        "faithfulness": f_score, "faithfulness_reason": f_reason,
        "context_relevance": r_score, "context_relevance_reason": r_reason,
        "completeness": c_score, "completeness_reason": c_reason,
    }


def run_config(q: dict, contexts: list[str], retrieval_info: dict) -> dict:
    """Generate the grounded answer for one config's contexts, score it, and
    package the result. Computation only — no printing. This is the per-config
    leaf of evaluate()'s structured result."""
    answer_text = answer(q["question"], contexts)
    return {
        "answer": answer_text,
        "contexts": contexts,
        "n_chunks": len(contexts),
        "metrics": score_answer(q, contexts, answer_text),
        "retrieval": retrieval_info,
    }


def _retrieval_info(role, subjects_applied, top_k_requested, pool, selected) -> dict:
    violation, violating_sources = audience_violation(pool, role)
    return {
        "audience": role,
        "subjects_applied": subjects_applied,
        "top_k_requested": top_k_requested,
        "candidate_pool": pool,
        "selected": selected,
        "security_violation": violation,
        "security_violating_sources": violating_sources,
    }


def evaluate_question(client, q: dict) -> dict:
    """Run one question through all five configs. plan_subjects runs exactly
    once here; rerank_all runs exactly twice (once for the rerank-only pool,
    once — shared — for the filter+rerank pool)."""
    role, question = q["audience"], q["question"]
    planned_subjects = plan_subjects(question)  # ONE call, reused below

    configs = {}

    # 1. baseline — no subject filter, vector top-4, no rerank.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=None, top_k=BASELINE_TOP_K))
    selected = [{**c, "final_rank": c["vector_rank"]} for c in pool]
    configs["baseline"] = run_config(
        q, [c["text"] for c in pool],
        _retrieval_info(role, None, BASELINE_TOP_K, pool, selected),
    )

    # 2. filter-only — subject filter (reused plan), vector top-4, no rerank.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=planned_subjects, top_k=BASELINE_TOP_K))
    selected = [{**c, "final_rank": c["vector_rank"]} for c in pool]
    configs["filter-only"] = run_config(
        q, [c["text"] for c in pool],
        _retrieval_info(role, planned_subjects, BASELINE_TOP_K, pool, selected),
    )

    # 3. rerank-only — its OWN pool (no subject filter), N=10, rerank ONCE, static cut.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=None, top_k=CANDIDATE_POOL_SIZE))
    ranked = rerank_all(question, pool)  # ONE call
    annotate_rerank_scores(pool, ranked)
    static_selected, static_contexts = select_context(ranked, "static")
    configs["rerank-only"] = run_config(
        q, static_contexts,
        _retrieval_info(role, None, CANDIDATE_POOL_SIZE, pool, _rank_selected(static_selected)),
    )

    # 4 & 5. filter + rerank — ONE shared pool + ONE rerank call, cut two ways.
    pool = hits_to_candidates(knn_search(client, question, role, subjects=planned_subjects, top_k=CANDIDATE_POOL_SIZE))
    ranked = rerank_all(question, pool)  # ONE call, shared by static + dynamic
    annotate_rerank_scores(pool, ranked)

    static_selected, static_contexts = select_context(ranked, "static")
    configs["filter + rerank static"] = run_config(
        q, static_contexts,
        _retrieval_info(role, planned_subjects, CANDIDATE_POOL_SIZE, pool, _rank_selected(static_selected)),
    )

    dynamic_selected, dynamic_contexts = select_context(ranked, "dynamic")
    configs["filter + rerank dynamic"] = run_config(
        q, dynamic_contexts,
        _retrieval_info(role, planned_subjects, CANDIDATE_POOL_SIZE, pool, _rank_selected(dynamic_selected)),
    )

    return {
        "question": question,
        "audience": role,
        "expect_refusal": q["expect_refusal"],
        "planned_subjects": planned_subjects,
        "configs": configs,
    }


def mean(xs: list[float]) -> float | None:
    """Average of `xs`, or None if empty. None (not NaN) is used deliberately:
    it round-trips through JSON as null, and this structure is meant to be
    consumed directly, not just printed."""
    return sum(xs) / len(xs) if xs else None


def summarize(per_question: dict) -> dict:
    """Aggregate per-config averages across every question. Refusal questions
    contribute to refusal_ok only; content-judge lists only ever contain
    scores from non-refusal questions, so an all-refusal question set would
    correctly report those averages as None rather than a misleading 0.0."""
    summary = {}
    for name in CONFIG_NAMES:
        n_chunks, faith, ctx_rel, complete, refusal_ok = [], [], [], [], []
        violations = 0
        for q_result in per_question.values():
            cfg = q_result["configs"][name]
            n_chunks.append(cfg["n_chunks"])
            metrics = cfg["metrics"]
            if "refusal_ok" in metrics:
                refusal_ok.append(1.0 if metrics["refusal_ok"] else 0.0)
            else:
                faith.append(metrics["faithfulness"])
                ctx_rel.append(metrics["context_relevance"])
                complete.append(metrics["completeness"])
            if cfg["retrieval"]["security_violation"]:
                violations += 1
        summary[name] = {
            "n_chunks_avg": mean(n_chunks),
            "faithfulness_avg": mean(faith),
            "context_relevance_avg": mean(ctx_rel),
            "completeness_avg": mean(complete),
            "refusal_ok_avg": mean(refusal_ok),
            "security_violations": violations,
        }
    return summary


def evaluate(client, questions: list[dict]) -> dict:
    """Run every question through all five configs and return ONE structured,
    JSON-shaped result — no printing. Shape:

        {
          "metadata": {question_count, configs, candidate_pool_size,
                       static_top_k, dynamic_threshold, baseline_top_k},
          "questions": {question_id: evaluate_question(...) result, ...},
          "summary":   {config_name: {n_chunks_avg, faithfulness_avg,
                                       context_relevance_avg, completeness_avg,
                                       refusal_ok_avg, security_violations}, ...}
        }

    A future UI renders directly from this; report() below is just one
    consumer of it (the CLI table)."""
    per_question = {q["id"]: evaluate_question(client, q) for q in questions}
    return {
        "metadata": {
            "question_count": len(questions),
            "configs": list(CONFIG_NAMES),
            "candidate_pool_size": CANDIDATE_POOL_SIZE,
            "static_top_k": RERANK_STATIC_TOP_K,
            "dynamic_threshold": MIN_RERANK_SCORE,
            "baseline_top_k": BASELINE_TOP_K,
        },
        "questions": per_question,
        "summary": summarize(per_question),
    }


def _fmt(x: float | None, spec: str = ".2f") -> str:
    return "  n/a" if x is None else format(x, spec)


def report(results: dict) -> None:
    """Presentation layer only — every number here also lives in `results`."""
    meta = results["metadata"]
    print("\n" + "=" * 78)
    print("FILTER + RERANK MIX — measured effect (averages over the question set)")
    print("=" * 78)
    print(f"candidate pool N={meta['candidate_pool_size']}  static top-k={meta['static_top_k']}  "
          f"dynamic threshold={meta['dynamic_threshold']}  baseline top-k={meta['baseline_top_k']}")
    header = f"{'config':26} {'chunks':>7} {'faithful':>9} {'ctx_rel':>9} {'complete':>9} {'refuse_ok':>10} {'sec_viol':>9}"
    print(header)
    print("-" * len(header))
    for name in CONFIG_NAMES:
        s = results["summary"][name]
        print(f"{name:26} {_fmt(s['n_chunks_avg'], '.1f'):>7} {_fmt(s['faithfulness_avg']):>9} "
              f"{_fmt(s['context_relevance_avg']):>9} {_fmt(s['completeness_avg']):>9} "
              f"{_fmt(s['refusal_ok_avg']):>10} {s['security_violations']:>9}")
    print("\n'chunks' is the AVERAGE final context size each config fed the model — fixed at 4 for")
    print("baseline/filter-only and 3 for the static rerank configs, but VARIABLE for the dynamic")
    print("cut (candidate POOL size is fixed at N; final context size is what varies). 'sec_viol'")
    print("counts questions where an employee's retrieval returned a manager-only chunk — this")
    print("must read 0 for every config; a nonzero value is a retrieval bug, not a quality result.")


def main() -> None:
    client = opensearch_client()
    questions = load_questions()
    print(f"Evaluating {len(questions)} questions x {len(CONFIG_NAMES)} configs "
          "— this makes a lot of model calls (a few minutes).")
    report(evaluate(client, questions))


if __name__ == "__main__":
    main()
