"""Subject taxonomy + a Nova tagger that labels each article with subjects.

Part 2's planning-filter needs every chunk to carry topic labels. We assign them
per ARTICLE (file) with one forced Nova tool call each, then cache the result to
subjects.json so re-ingesting (and Part 5's revive) doesn't re-pay for tagging.
The planner (planner.py) maps a user question to the SAME enum, and the
intersection of {question's subjects} and {chunk's subjects} becomes an
OpenSearch filter.
"""
import json
import os
from pathlib import Path

import boto3
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
bedrock = boto3.client("bedrock-runtime", region_name=REGION)

CACHE_FILE = Path(__file__).resolve().parent / "subjects.json"

# One fixed, shared vocabulary. The tagger picks from it, the planner picks from
# it, the filter matches on it — so all three speak the same language. It spans
# BOTH corpora (handbook topics + manager-playbook topics).
#
# Deliberately BROAD (~9 buckets, not 30 fine-grained ones). A soft filter only
# helps if the tagger and the planner land on the SAME label — and broad buckets
# agree far more often than narrow ones. Fine-grained subjects shrink the pool
# more, but each extra subject is another chance for the two ends to disagree and
# filter out the chunk that had the answer. Chunks are multi-labeled, so a doc
# that spans two buckets carries both.
SUBJECTS = [
    "pay_and_benefits",               # compensation, insurance, retirement, perks, allowances
    "time_off_and_leave",             # vacation, holidays, sabbatical, parental/medical leave
    "severance_and_termination",      # severance pay + the offboarding/termination process
    "hiring_and_onboarding",          # recruiting, interviewing, new-hire onboarding
    "careers_titles_and_promotions",  # levels, titles, career growth, promotions
    "performance_and_feedback",       # reviews, performance management, feedback, coaching, recognition
    "managing_people",                # 1:1s, manager standards, difficult conversations, boundaries
    "devices_security_and_systems",   # work devices, internal tools, access, moonlighting/conflicts
    "company_culture_and_norms",      # rituals, how we work, getting started, general guidance
]

_TAG_TOOL = {
    "toolSpec": {
        "name": "tag_subjects",
        "description": "Record the subjects this internal document covers.",
        "inputSchema": {"json": {
            "type": "object", "additionalProperties": False, "required": ["subjects"],
            "properties": {"subjects": {
                "type": "array",
                "description": "Every subject the article substantially covers (1-3 is typical).",
                "items": {"type": "string", "enum": SUBJECTS},
            }},
        }},
    }
}


def tag_article(text: str) -> list[str]:
    """Ask Nova which SUBJECTS an article covers. A FORCED tool call gives
    structured, enum-constrained output (Nova 2 Lite supports forced toolChoice),
    so we get back a clean list from the allowed vocabulary — no parsing prose."""
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text":
            "Classify this internal document by subject. Pick every subject it "
            "substantially covers from the allowed list.\n\n" + text[:6000]}]}],
        toolConfig={"tools": [_TAG_TOOL], "toolChoice": {"tool": {"name": "tag_subjects"}}},
    )
    for block in resp["output"]["message"]["content"]:
        if "toolUse" in block:
            picked = block["toolUse"]["input"].get("subjects", [])
            return list(dict.fromkeys(s for s in picked if s in SUBJECTS))  # valid + deduped
    return []


def load_or_tag(articles: dict[str, str]) -> dict[str, list[str]]:
    """articles: {key: full_text}. Returns {key: [subjects]}, cached to
    subjects.json so tagging runs once — Nova is called only on a cache miss."""
    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
    changed = False
    for key, text in articles.items():
        if key not in cache:
            cache[key] = tag_article(text)
            print(f"  tagged {key}: {', '.join(cache[key]) or '(none)'}")
            changed = True
    if changed:
        CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return cache
