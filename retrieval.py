"""Filtered k-NN retrieval + grounded answer generation.

THREE filters live here, and they differ by where the filter VALUE comes from
and by how they fail:
  - ACCESS (audience) — ROLE-forced, hard security. The value comes from WHO the
    user is: an employee may only see audience='all'; a manager sees everything.
    Always applied. Fails CLOSED (see access_filter).
  - SUBJECT (subjects) — LLM-planned, soft. The value comes from the QUESTION
    (planner.py, not in this module): narrows the pool to chunks carrying one of
    the planned subjects. Fails OPEN — an empty/None plan adds no clause.
  - RECENCY (last_updated) — USER-supplied, soft. An explicit "updated on or
    after this date" cutoff. Off unless a date is given; no default window.

All three are `term` / `terms` / `range` clauses on the metadata fields, combined
into ONE `bool.must` and passed as the k-NN query's inner `filter` — never as a
top-level `post_filter`. Filtering inside the k-NN block means the engine only
ever visits chunks that pass the filter DURING the vector search, so an employee
never sees a manager-only chunk even transiently in the ranking.

`knn_search` returns raw OpenSearch hits (not just text): the planner/reranker/
eval layers and the security tests all need `audience`, `subjects` and
`last_updated` off each hit, not only its text.
"""
import logging
import os
from typing import TypedDict

from client import INDEX_NAME, TOP_K, bedrock, embed_text

logger = logging.getLogger(__name__)

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]

SYSTEM = (
    "You are the NovaOps assistant. Answer the question using ONLY the provided "
    "context chunks. If the context does not contain the answer, say so plainly — "
    "do not use outside knowledge or guess."
)

# The single source of truth for who is allowed to ask at all. access_filter()
# validates against this SET before deciding a policy — an audience that isn't
# in it is refused outright, never treated as "manager" by falling through an
# if/else. Adding a role later means adding it here AND giving it an explicit
# branch in access_filter(); it must never be enough to just widen this set.
SUPPORTED_AUDIENCES = frozenset({"employee", "manager"})


class Hit(TypedDict):
    _score: float
    _source: dict


class UnsupportedAudienceError(ValueError):
    """Raised when access_filter() is asked for a role outside SUPPORTED_AUDIENCES.

    A ValueError subclass rather than bare ValueError: callers that want to
    catch this specific security rejection can, while `except ValueError` still
    works for anyone who doesn't need the distinction. No new dependency."""


def access_filter(audience: str) -> list[dict]:
    """The hard security boundary: employee -> only company-wide chunks;
    manager -> no restriction (sees all). Fails CLOSED — an audience outside
    SUPPORTED_AUDIENCES is REJECTED (raises), never silently treated as
    unrestricted. Unknown must never be more permissive than the narrowest
    known role, let alone as permissive as the broadest one."""
    if audience not in SUPPORTED_AUDIENCES:
        raise UnsupportedAudienceError(
            f"Unsupported audience {audience!r}; expected one of {sorted(SUPPORTED_AUDIENCES)}."
        )
    return [{"term": {"audience": "all"}}] if audience == "employee" else []


def subject_terms(subjects: list[str] | None) -> list[dict]:
    """`terms` matches a chunk if ITS subjects array contains ANY listed subject.
    None or [] means "don't filter" — the fail-open quality lever."""
    return [{"terms": {"subjects": subjects}}] if subjects else []


def recency_range(updated_after: str | None) -> list[dict]:
    """A `range` on the date field: keep chunks whose document was updated on or
    after the user's cutoff ('yyyy-MM-dd'). None means no recency constraint —
    there is no default window."""
    return [{"range": {"last_updated": {"gte": updated_after}}}] if updated_after else []


def build_filter(
    audience: str, subjects: list[str] | None = None, updated_after: str | None = None
) -> dict | None:
    """Compose the active clauses into ONE bool/must: `must` means AND, so a
    chunk has to satisfy every active clause to pass. A clause that's off
    contributes [] and drops out of the AND. Returns None (not an empty
    {"bool": {"must": []}}) when nothing is active, so knn_search runs
    UNfiltered rather than with a filter that (harmlessly, but confusingly)
    matches everything."""
    must = access_filter(audience) + subject_terms(subjects) + recency_range(updated_after)
    return {"bool": {"must": must}} if must else None


def knn_search(
    client,
    query: str,
    audience: str,
    subjects: list[str] | None = None,
    top_k: int = TOP_K,
    updated_after: str | None = None,
) -> list[Hit]:
    """Embed `query`, run a filtered k-NN, return the raw hits in vector-search
    order. `top_k` is both the candidate-pool size (e.g. 10, for reranking) and
    the plain result count (e.g. 4, for the unreranked baseline) — one knob, no
    second hard-coded pool size.

    The filter sits INSIDE the `knn` block, so the engine applies it DURING the
    HNSW graph walk — the search only ever visits chunks that pass the filter
    and returns top_k FROM that subset. A `post_filter` would instead rank
    against the whole corpus and discard misses afterward, which can silently
    hand back fewer than top_k and briefly ranks chunks the caller must never
    see. `_source` includes every metadata field the reranker, the answer step
    and the eval's security checks need — not just `text`.

    Audience is validated (via build_filter -> access_filter) BEFORE embedding
    the query or touching `client` — an unsupported audience raises and no
    embedding call or OpenSearch request is made."""
    filt = build_filter(audience, subjects, updated_after)
    logger.debug(
        "knn_search audience=%s subjects=%s top_k=%s updated_after=%s filtered=%s",
        audience, subjects, top_k, updated_after, filt is not None,
    )
    knn: dict = {"vector": embed_text(query), "k": top_k}
    if filt:
        knn["filter"] = filt
    body = {
        "size": top_k,
        "query": {"knn": {"vector": knn}},
        "_source": ["text", "source", "corpus", "audience", "subjects", "last_updated"],
    }
    hits = client.search(index=INDEX_NAME, body=body)["hits"]["hits"]
    logger.debug("knn_search returned %d hits", len(hits))
    return hits


def count_candidates(
    client, audience: str, subjects: list[str] | None = None, updated_after: str | None = None
) -> int:
    """How many chunks the given filter admits — the candidate-pool size before
    ranking. Uses the SAME build_filter as knn_search, so this always answers
    "how many chunks would this exact filter combination search", never a
    parallel notion of "narrowing". Falls back to match_all when no filter is
    active (build_filter returns None for an unrestricted manager query)."""
    filt = build_filter(audience, subjects, updated_after) or {"match_all": {}}
    return client.count(index=INDEX_NAME, body={"query": filt})["count"]


def answer(question: str, contexts: list[str]) -> str:
    """One Bedrock Converse call, grounded in `contexts` only. `contexts` must
    already be ordered most-relevant-first (vector order for an unreranked
    config, reranked order otherwise) — the prompt tells the model that and
    asks it to weight earlier chunks more, while still allowed to pull a needed
    detail from a later one (a lower chunk can carry the one fact the answer
    needs)."""
    ctx = "\n\n".join(f"[chunk {i + 1}]\n{c}" for i, c in enumerate(contexts))
    prompt = (
        f"Context — chunks are ordered by relevance, most relevant first:\n{ctx}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the context above. Give more weight to the earlier chunks, "
        "but still use a later chunk when it holds a detail the answer needs."
    )
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        # maxTokens caps the ANSWER, not the context. The multi-step manager
        # questions in eval_questions.jsonl need ~450-570 tokens; a smaller cap
        # cuts them off mid-sentence.
        inferenceConfig={"maxTokens": 1000, "temperature": 0.2},
    )
    return resp["output"]["message"]["content"][0]["text"]
