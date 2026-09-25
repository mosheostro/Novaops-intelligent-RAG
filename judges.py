"""Four LLM-as-judge metrics for RAG answers: three scores, plus a refusal check.

Every judge is one Nova call, built the same way so they're easy to read and to
add to:
  - a SYSTEM prompt holds the RUBRIC — the judge's role and what the output means;
  - the user message is a few LABELLED sections (question / context / answer / facts);
  - the result comes back through a FORCED tool call, so we always get clean
    structured output instead of parsing prose.

LLM judges are cheap, need no labelled golden answers, and catch the most common
RAG failures. They do NOT prove an answer is fully correct — for that you'd need a
labelled set and metrics like Recall@k / Precision@k / MRR (production/eval-track).

The four judges, and why each moves when you change retrieval:
  - faithfulness      — is every claim in the answer supported by the context?
  - context_relevance — what fraction of the retrieved chunks are on-topic?
  - completeness      — what fraction of the question's required facts are in the answer?
                        (A large top_k can BURY a needed fact in noise; too small a
                        top_k can DROP it — completeness catches both.)
  - refusal           — did the answer decline to answer the question at all? Judged
                        by the model reading the whole response, never by keyword
                        matching — a phrase like "do not have" can occur naturally
                        inside a genuine answer and must not be misread as a refusal.

Provided plumbing: the four LLM judges your eval imports to score answers.
"""
import os

from dotenv import find_dotenv, load_dotenv

from client import bedrock

load_dotenv(find_dotenv())
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]

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


REFUSAL_RUBRIC = (
    "You are a strict evaluator determining whether an ASSISTANT RESPONSE is a "
    "refusal to answer the QUESTION.\n"
    "  true  = the assistant refuses to answer, says the information is "
    "unavailable or insufficient, or otherwise declines to provide an answer.\n"
    "  false = the assistant attempts to answer the question, even if the answer "
    "may be incorrect, incomplete, or poorly supported.\n"
    "Evaluate the response AS A WHOLE. Do not classify based on individual phrases "
    "or keywords — a phrase such as \"do not have\" can occur naturally inside a "
    "valid answer and does not by itself indicate refusal.\n"
    "Do not evaluate factual correctness, completeness, or faithfulness to any "
    "context. Only determine whether the response is a refusal."
)

# A separate forced tool from _SCORE_TOOL: a refusal is a yes/no classification,
# not a point on a 0.0-1.0 scale, so it gets its own boolean-shaped contract
# rather than being squeezed into the score tool's number.
_REFUSAL_TOOL = {
    "toolSpec": {
        "name": "submit_refusal_judgment",
        "description": "Submit whether the assistant response refused to answer the question.",
        "inputSchema": {"json": {
            "type": "object", "additionalProperties": False, "required": ["refused", "reason"],
            "properties": {
                "refused": {
                    "type": "boolean",
                    "description": "true if the response refused to answer; false if it attempted an answer.",
                },
                "reason": {"type": "string", "description": "One short sentence justifying the judgment."},
            },
        }},
    }
}


def _run_refusal_judge(rubric: str, sections: list[tuple[str, str]]) -> tuple[bool, str]:
    """Same shape as _run_judge (system=rubric, labelled user sections, forced
    tool, temperature 0.0), but for the boolean submit_refusal_judgment tool
    instead of the numeric submit_score tool."""
    user_message = "\n\n".join(f"### {label}\n{body}" for label, body in sections)
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": rubric}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        toolConfig={"tools": [_REFUSAL_TOOL], "toolChoice": {"tool": {"name": "submit_refusal_judgment"}}},
        inferenceConfig={"temperature": 0.0},   # a judge should score the same input the same way
    )
    for block in resp["output"]["message"]["content"]:
        if "toolUse" in block:
            result = block["toolUse"]["input"]
            return bool(result.get("refused", False)), result.get("reason", "")
    return False, ""


def refusal(question: str, answer: str) -> bool:
    """LLM judge (not a keyword heuristic): did `answer` refuse to answer
    `question`? Used for the refusal cases — a manager-only or unanswerable
    question a correct pipeline should NOT answer. Judges the response as a
    whole; never searches for substrings, so a legitimate answer that happens
    to contain a phrase like "do not have" is not misclassified as a refusal."""
    refused_flag, _reason = _run_refusal_judge(REFUSAL_RUBRIC, [
        ("QUESTION", question),
        ("ASSISTANT RESPONSE", answer),
    ])
    return refused_flag
