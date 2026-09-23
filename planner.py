"""Map a user question to the subjects worth searching — the planning-filter.

Instead of vector-searching the whole corpus, first ask Nova which SUBJECTS the
question touches (a forced tool call over the SAME enum as the tagger), then
search ONLY chunks tagged with those subjects. That shrinks the candidate pool
before k-NN even runs.

The subject filter is a QUALITY filter, not a security one — so it must FAIL
OPEN. The access filter (retrieval.py's `audience`) fails CLOSED: when in
doubt, deny. This one is the opposite: when in doubt, DON'T filter. Two ways we
hold that line:

  1. Recall-biased planning — pick EVERY plausibly-relevant subject, not just the
     single best one. With OR-matching, a wider plan means a gray-zone question
     still reaches the right chunk. Over-including a subject is cheap; missing one
     hides the answer.
  2. Empty plan -> no filter — if the question is broad or the planner can't map
     it confidently, it returns an empty list and the caller searches everything.
     Better a bigger pool than a filtered-out answer.

A valid empty plan is NOT the same as a failure: if the Bedrock call itself
raises (network, throttling, auth, ...), that exception propagates — it is a
technical failure, not a considered "search everything" decision, and must not
be swallowed into a silent [].

Even so recall-biasing is a trick, not a guarantee, which is why the eval
MEASURES it (watch completeness — that's what catches a filter that dropped a
needed fact).
"""
import os

from client import bedrock
from subjects import SUBJECTS

MODEL_ID = os.environ["BEDROCK_MODEL_ID"]

_PLAN_TOOL = {
    "toolSpec": {
        "name": "pick_subjects",
        "description": "Pick the subjects worth searching to answer the user's question.",
        "inputSchema": {"json": {
            "type": "object", "additionalProperties": False, "required": ["subjects"],
            "properties": {"subjects": {
                "type": "array",
                "description": (
                    "Every subject that could plausibly hold the answer — include an extra "
                    "rather than risk missing one. Return an EMPTY list if the question is "
                    "broad or you can't confidently map it: that searches everything."
                ),
                "items": {"type": "string", "enum": SUBJECTS},
            }},
        }},
    }
}


def plan_subjects(question: str) -> list[str]:
    """Return the subjects Nova thinks the question needs (subset of SUBJECTS), or
    an empty list to mean 'don't filter' (fail open — see the module docstring).
    Does NOT catch exceptions from the Bedrock call itself; a technical failure
    must propagate, not be mistaken for a considered empty plan."""
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text":
            "Which subjects should we search to answer this question? Include every "
            "subject that could plausibly hold the answer; return an empty list if the "
            f"question is broad or you can't map it confidently.\n\nQuestion: {question}"}]}],
        toolConfig={"tools": [_PLAN_TOOL], "toolChoice": {"tool": {"name": "pick_subjects"}}},
    )
    for block in resp["output"]["message"]["content"]:
        if "toolUse" in block:
            picked = block["toolUse"]["input"].get("subjects", [])
            return list(dict.fromkeys(s for s in picked if s in SUBJECTS))  # valid + deduped
    return []


if __name__ == "__main__":
    # Quick manual check: python planner.py "how much parental leave do I get?"
    import sys
    q = " ".join(sys.argv[1:]) or "how much parental leave do I get?"
    print(f"Q: {q}\nplanned subjects: {plan_subjects(q)}")
