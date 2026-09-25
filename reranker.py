"""Rerank retrieved candidates with Nova — a second, more careful relevance pass.

Vector similarity is cheap and approximate: it returns a good top-N, but the BEST
chunk is not always ranked #1 — cosine over an embedding is a coarse signal. A
reranker re-scores each candidate against the query with a stronger one. Here the
"cross-encoder" is Nova itself: we hand it the query + all N candidates in ONE
call and ask for a relevance score per candidate (a forced tool call, so the
scores come back structured).

A reranker score is a DIFFERENT distribution than the vector `_score` retrieval.py
returns — never compare the two numbers directly; judge the reranker by whether
the right chunk rises to the top.

This module only RANKS — it does not decide how many candidates survive. The
caller (eval.py) cuts the ranked list: a fixed top_k, or a score threshold. That
keeps "how good is this candidate" and "how many do we keep" as separate
decisions.
"""
import logging
import os

from client import bedrock

logger = logging.getLogger(__name__)

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]

_RERANK_TOOL = {
    "toolSpec": {
        "name": "rank",
        "description": "Score every candidate passage for relevance to the query.",
        "inputSchema": {"json": {
            "type": "object", "additionalProperties": False, "required": ["scores"],
            "properties": {"scores": {
                "type": "array",
                "description": "One entry per candidate, referenced by the [index] shown.",
                "items": {
                    "type": "object", "additionalProperties": False, "required": ["index", "score"],
                    "properties": {
                        "index": {"type": "integer", "description": "The candidate's [index]."},
                        "score": {"type": "number", "description": "Relevance from 0.0 to 1.0."},
                    },
                },
            }},
        }},
    }
}


def rerank_all(query: str, candidates: list[dict]) -> list[tuple[dict, float]]:
    """Score EVERY candidate (dicts with a 'text') against the query in ONE Nova
    call and return them as (candidate, score) pairs, the best first. Callers decide
    how to CUT the list (a fixed top_k, or a score threshold) — this function
    only ranks.

    The WHOLE chunk goes to the reranker — chunks are small, and scoring a
    truncated fragment would rank on evidence the answer and the judges never
    see, so the reranker's order would be built on different text than
    everything downstream.

    A candidate the model's response omits, or whose score entry is malformed
    (a non-numeric score, a missing "score" key, an out-of-range or noninteger
    "index"), scores 0.0 rather than raising — one bad entry in a listwise
    response must not throw away the scores for every other candidate. The sort
    is stable, so tied scores keep their original candidate order."""
    logger.debug("rerank_all: scoring %d candidates", len(candidates))
    listing = "\n\n".join(f"[{i}] {c['text']}" for i, c in enumerate(candidates))
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text":
            f"Query: {query}\n\nScore each candidate passage from 0.0 to 1.0 for how well it "
            f"helps answer the query. Use the exact [index] shown for each.\n\n{listing}"}]}],
        toolConfig={"tools": [_RERANK_TOOL], "toolChoice": {"tool": {"name": "rank"}}},
    )
    scores: dict[int, float] = {}
    for block in resp["output"]["message"]["content"]:
        if "toolUse" not in block:
            continue
        for entry in block["toolUse"]["input"].get("scores", []):
            i = entry.get("index")
            if not isinstance(i, int) or isinstance(i, bool) or not (0 <= i < len(candidates)):
                continue
            try:
                scores[i] = max(0.0, min(1.0, float(entry.get("score", 0.0))))
            except (TypeError, ValueError):
                continue  # malformed score for this one candidate — skip it, not the whole call
    omitted = [i for i in range(len(candidates)) if i not in scores]
    if omitted:
        logger.warning(
            "rerank_all: %d of %d candidates got no usable score from the model "
            "(defaulted to 0.0)", len(omitted), len(candidates),
        )
    if scores:
        values = list(scores.values())
        logger.debug(
            "rerank_all: scores min=%.2f max=%.2f mean=%.2f",
            min(values), max(values), sum(values) / len(values),
        )
    order = sorted(range(len(candidates)), key=lambda i: scores.get(i, 0.0), reverse=True)
    return [(candidates[i], scores.get(i, 0.0)) for i in order]


def rerank(query: str, candidates: list[dict], top_k: int) -> list[tuple[dict, float]]:
    """Fixed-count cut: the top_k most relevant candidates, the best first."""
    return rerank_all(query, candidates)[:top_k]
