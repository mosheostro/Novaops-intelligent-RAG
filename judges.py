"""Three LLM-as-judge metrics for RAG answers, plus a refusal check.

Every metric is one Nova call, built the same way so they're easy to read and to
add to:
  - a SYSTEM prompt holds the RUBRIC — the judge's role and what 0.0 vs 1.0 mean;
  - the user message is a few LABELLED sections (question / context / answer / facts);
  - the score comes back through a FORCED tool call (`submit_score`), so we always
    get a clean {score, reason} instead of parsing a number out of prose.

LLM judges are cheap, need no labelled golden answers, and catch the most common
RAG failures. They do NOT prove an answer is fully correct — for that you'd need a
labelled set and metrics like Recall@k / Precision@k / MRR (production/eval-track).

The three metrics, and why each moves when you change retrieval:
  - faithfulness      — is every claim in the answer supported by the context?
  - context_relevance — what fraction of the retrieved chunks are on-topic?
  - completeness      — what fraction of the question's required facts are in the answer?
                        (A large top_k can BURY a needed fact in noise; too small a
                        top_k can DROP it — completeness catches both.)

Provided plumbing: the three LLM judges your eval imports to score answers.
"""
import os

import boto3
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

# One shared scoring tool for all three judges. Forcing it (toolChoice) guarantees
# a structured {score, reason} — no free-text parsing. What the 0.0-1.0 scale MEANS
# is defined per-metric in each judge's rubric (the system prompt), not here.
_SCORE_TOOL = {
    "toolSpec": {
        "name": "submit_score",
        "description": "Submit the evaluation score for the answer under review.",
        "inputSchema": {"json": {
            "type": "object", "additionalProperties": False, "required": ["score", "reason"],
            "properties": {
                "score": {"type": "number", "description": "A value from 0.0 (worst) to 1.0 (best), per the rubric."},
                "reason": {"type": "string", "description": "One short sentence justifying the score."},
            },
        }},
    }
}


def _run_judge(rubric: str, sections: list[tuple[str, str]]) -> tuple[float, str]:
    """One judge call. `rubric` becomes the system prompt; `sections` are the
    labelled blocks of the user message ([(label, text), ...]); the score returns
    through the forced `submit_score` tool as (score, reason)."""
    user_message = "\n\n".join(f"### {label}\n{body}" for label, body in sections)
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": rubric}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        toolConfig={"tools": [_SCORE_TOOL], "toolChoice": {"tool": {"name": "submit_score"}}},
        inferenceConfig={"temperature": 0.0},   # a judge should score the same input the same way
    )
    for block in resp["output"]["message"]["content"]:
        if "toolUse" in block:
            result = block["toolUse"]["input"]
            score = max(0.0, min(1.0, float(result.get("score", 0.0))))
            return score, result.get("reason", "")
    return 0.0, ""


# --- the rubrics (each defines its own 0.0-1.0 scale) --------------------------

FAITHFULNESS_RUBRIC = (
    "You are a strict RAG evaluator scoring FAITHFULNESS — whether the ANSWER is "
    "grounded in the retrieved CONTEXT.\n"
    "  1.0 = every claim in the answer is supported by the context.\n"
    "  0.0 = the answer states claims the context does not support.\n"
    "Judge support by the CONTEXT only; ignore whether a claim happens to be true "
    "in the real world."
)

CONTEXT_RELEVANCE_RUBRIC = (
    "You are a strict RAG evaluator scoring CONTEXT RELEVANCE — the PROPORTION of "
    "retrieved chunks that are on-topic for the QUESTION.\n"
    "Label each numbered chunk independently as relevant (it helps answer the "
    "question) or not, then:\n"
    "  score = (number of relevant chunks) / (total number of chunks).\n"
    "IMPORTANT: do NOT score by whether the answer is present. An off-topic chunk "
    "MUST lower the score even if OTHER chunks already fully answer the question. "
    "Example: 2 on-topic and 1 off-topic chunk = 0.67, never 1.0."
)

COMPLETENESS_RUBRIC = (
    "You are a strict RAG evaluator scoring COMPLETENESS — whether the ANSWER "
    "includes the facts the QUESTION requires.\n"
    "  score = the fraction of the REQUIRED FACTS that the answer actually states.\n"
    "  1.0 = all required facts present, 0.0 = none. Each missing required fact "
    "lowers the score."
)


# --- the three judges: assemble sections, run the rubric -----------------------

def faithfulness(question: str, contexts: list[str], answer: str) -> tuple[float, str]:
    return _run_judge(FAITHFULNESS_RUBRIC, [
        ("QUESTION", question),
        ("CONTEXT", "\n\n".join(contexts)),
        ("ANSWER", answer),
    ])


def context_relevance(question: str, contexts: list[str]) -> tuple[float, str]:
    numbered = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(contexts))
    return _run_judge(CONTEXT_RELEVANCE_RUBRIC, [
        ("QUESTION", question),
        ("RETRIEVED CHUNKS", numbered),
    ])


def completeness(question: str, key_facts: list[str], answer: str) -> tuple[float, str]:
    facts = "\n".join(f"- {fact}" for fact in key_facts)
    return _run_judge(COMPLETENESS_RUBRIC, [
        ("QUESTION", question),
        ("REQUIRED FACTS", facts),
        ("ANSWER", answer),
    ])


def refused(answer: str) -> bool:
    """Heuristic (not an LLM call): did the answer decline / say the info isn't in
    the context? Used for the refusal cases — a manager-only or unanswerable
    question a correct pipeline should NOT answer."""
    lowered = answer.lower()
    cues = [
        "don't have", "do not have", "isn't in", "is not in", "not in the context",
        "no information", "not available", "cannot answer", "can't answer",
        "unable to", "does not contain", "doesn't contain", "not provided",
    ]
    return any(cue in lowered for cue in cues)
