"""Answer ONE ad-hoc question with ONE configuration — the entry point the UI
calls. Same retrieval / rerank / selection steps as eval.py's
evaluate_question(), reusing its helpers rather than copying them; the only
difference is that a single config runs, and judging is optional.
"""
import logging
from datetime import date

from eval import (
    BASELINE_TOP_K,
    CANDIDATE_POOL_SIZE,
    _select_all,
    attach_rerank_scores,
    build_retrieval_result,
    build_selection_result,
    hits_to_candidates,
    rerank_candidates,
    select_context,
)
from judges import context_completeness, context_relevance, faithfulness, refusal
from models import CONFIG_NAMES, AskResult, ConfigName, LiveJudgement
from planner import plan_subjects
from retrieval import access_filter, answer, knn_search

logger = logging.getLogger(__name__)

_PLANNED = {"filter-only", "filter + rerank static", "filter + rerank dynamic"}
_RERANKED = {"rerank-only": "static", "filter + rerank static": "static", "filter + rerank dynamic": "dynamic"}


def ask(
    client, question: str, role: str, config: ConfigName, judge: bool = False, cutoff: date | None = None,
) -> AskResult:
    """`cutoff` keeps only chunks with `last_updated >= cutoff` (inclusive); None
    means no recency constraint. It narrows whatever `config` retrieves and never
    replaces the access filter, which is always applied from `role`."""
    if config not in CONFIG_NAMES:
        raise ValueError(f"unknown config: {config!r}")
    # Fail closed BEFORE spending any planner/Bedrock call: access_filter is the
    # single source of truth for which roles may ask at all.
    access_filter(role)

    subjects = plan_subjects(question) if config in _PLANNED else None
    top_k = CANDIDATE_POOL_SIZE if config in _RERANKED else BASELINE_TOP_K
    updated_after = cutoff.isoformat() if cutoff else None  # the index's last_updated format: yyyy-MM-dd
    pool = hits_to_candidates(
        knn_search(client, question, role, subjects=subjects, top_k=top_k, updated_after=updated_after)
    )

    if config in _RERANKED:
        pool, ranked = attach_rerank_scores(pool, rerank_candidates(question, pool))
        selection = build_selection_result(select_context(ranked, _RERANKED[config]))
    else:
        selection = _select_all(pool)
    retrieval = build_retrieval_result(role, subjects, top_k, pool, cutoff=cutoff)

    answer_text = answer(question, selection.context_texts)
    judgement = None
    if judge:
        f_score, f_reason = faithfulness(question, selection.context_texts, answer_text)
        r_score, r_reason = context_relevance(question, selection.context_texts)
        refused = refusal(question, answer_text)
        c_score = c_reason = None
        # No usable context (zero selected chunks, or the answer refused): skip the
        # judge — no Bedrock call — and report completeness as not applicable.
        if selection.status == "selected" and not refused:
            c_score, c_reason = context_completeness(question, selection.context_texts, answer_text)
        judgement = LiveJudgement(
            faithfulness=f_score, faithfulness_reason=f_reason,
            context_relevance=r_score, context_relevance_reason=r_reason,
            refused=refused, completeness=c_score, completeness_reason=c_reason,
        )

    logger.info("ask completed config=%s audience=%s n_chunks=%d judged=%s",
                config, role, len(selection.chunks), judge)
    return AskResult(
        question=question, audience=role, config=config, planned_subjects=subjects,
        retrieval=retrieval, selection=selection, answer=answer_text, judgement=judgement,
    )
