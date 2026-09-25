"""Ingest both corpora into ONE index, tagged with metadata from each doc.

Every document starts with a frontmatter header, e.g.:

    ---
    last_updated: 2025-03-07
    corpus: handbook
    audience: all
    ---

We parse that header (authoritative) and index three metadata fields per chunk —
each powering a different KIND of filter (see retrieval.py):
  - audience     -> the ROLE-forced access filter (hard security).
  - subjects     -> Nova tags the article; powers the LLM-planned subject filter.
  - last_updated -> powers the USER-supplied recency filter.

The frontmatter is metadata, not content, so we strip it before chunking/embedding.

This script is NOT the index's lifecycle manager: it only ever ADDS chunks. It
never deletes the index, never recreates it, never deletes existing documents,
and never touches the mapping (create_index.py owns index creation; teardown is
a separate, explicit operation elsewhere). Running this against an already-
populated index adds another batch of records rather than refusing or
replacing anything — that is the existing, unchanged ingestion semantics.

    python create_index.py   # once, first (adds the metadata fields)
    python ingest.py
"""
import logging
import time
from pathlib import Path

from opensearchpy import helpers

from client import INDEX_NAME, embed_text, opensearch_client
from subjects import load_or_tag

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"

CHUNK_WORDS = 250
OVERLAP_WORDS = 50


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a '---'-fenced header from the body. Returns (meta, body). The header
    is flat 'key: value' lines — no YAML library needed."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)           # ['', '\nkey: val\n...', '\nbody...']
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip("\n")


def chunk_document(text: str) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + CHUNK_WORDS]))
        if start + CHUNK_WORDS >= len(words):
            break
        start += CHUNK_WORDS - OVERLAP_WORDS
    return chunks


def load_documents_with_metadata() -> list[dict]:
    """Read every .md file under DATA_DIR (the project-level data/, not
    reference/) and split its frontmatter METADATA from its body TEXT. Returns
    one dict per FILE (not per chunk) — build_records() chunks them later, after
    the subject tagger has seen each whole document."""
    documents = []
    for corpus_dir in sorted(p for p in DATA_DIR.iterdir() if p.is_dir()):
        for path in sorted(corpus_dir.glob("*.md")):
            meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            documents.append({
                "key": f"{corpus_dir.name}/{path.name}",       # unique id across corpora
                "corpus": meta.get("corpus", corpus_dir.name),
                "audience": meta.get("audience", "all"),        # access metadata
                "last_updated": meta.get("last_updated"),       # recency metadata
                "source": path.name,
                "text": body,                                   # body only — frontmatter stripped
            })
    return documents


def ensure_index_ready_for_ingest(client) -> None:
    """The populated-index guard. Runs BEFORE any tagging, embedding, or bulk
    call, so an accidental re-run against the live, already-populated index
    costs nothing beyond one exists()/count() check:

      - index missing      -> refuse; tell the caller to run create_index.py first.
      - index empty (0 docs) -> proceed; ingestion is safe.
      - index non-empty     -> refuse; report the current count.

    This is deliberately NOT an upsert/idempotency mechanism — it only decides
    whether ingestion may run at all. It never deletes, recreates, or modifies
    the mapping; those stay someone else's responsibility."""
    if not client.indices.exists(index=INDEX_NAME):
        logger.error("index '%s' does not exist", INDEX_NAME)
        raise SystemExit(
            f"Index '{INDEX_NAME}' does not exist. Run create_index.py first, then re-run ingest.py."
        )
    count = client.count(index=INDEX_NAME)["count"]
    if count > 0:
        logger.error("index '%s' already has %d document(s); refusing to ingest", INDEX_NAME, count)
        raise SystemExit(
            f"Index '{INDEX_NAME}' already contains {count} document(s) — refusing to ingest "
            "to avoid indexing a duplicate copy of the corpus. This script has no upsert/"
            "idempotency logic; it only ever adds records."
        )


def wait_until_indexed(client, expected: int, timeout: int = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.count(index=INDEX_NAME)["count"] >= expected:
                return
        except Exception:
            pass
        time.sleep(2)
    print("  (still finalizing — documents may take a few more seconds to appear)")


def build_records(documents: list[dict], tags: dict) -> list[dict]:
    """Chunk each document and attach its metadata — one record per chunk (no
    vector yet)."""
    records = []
    for doc in documents:
        for chunk in chunk_document(doc["text"]):
            records.append({
                "text": chunk,
                "source": doc["source"],
                "corpus": doc["corpus"],
                "audience": doc["audience"],           # role-forced access filter
                "subjects": tags[doc["key"]],          # LLM-planned subject filter
                "last_updated": doc["last_updated"],   # user-supplied recency filter
            })
    return records


def embed_records(records: list[dict]) -> None:
    """Add a Titan embedding vector to each record, in place — one call per chunk."""
    for i, rec in enumerate(records, start=1):
        rec["vector"] = embed_text(rec["text"])
        if i % 25 == 0 or i == len(records):
            print(f"  embedded {i}/{len(records)}")


def index_records(client, records: list[dict]) -> None:
    """Bulk-index the records, then wait until they're searchable. aoss auto-
    assigns document ids, so we do NOT set _id (Serverless rejects a caller-
    supplied id)."""
    actions = [{"_index": INDEX_NAME, "_source": rec} for rec in records]
    helpers.bulk(client, actions)
    wait_until_indexed(client, len(records))
    print(f"Indexed {len(records)} chunks (audience + subjects + last_updated) into '{INDEX_NAME}'.")
    logger.info("indexed %d chunks into '%s'", len(records), INDEX_NAME)


def main() -> None:
    # This main() IS the ingest pipeline — read it top to bottom, one stage per line.
    logger.info("ingest started")
    client = opensearch_client()                                  # open the OpenSearch client
    ensure_index_ready_for_ingest(client)                         # refuse if missing or already populated
    documents = load_documents_with_metadata()                    # read each .md; split frontmatter (audience/corpus/date) from the body
    print(f"Tagging {len(documents)} documents with subjects (cached after the first run)...")
    tags = load_or_tag({d["key"]: d["text"] for d in documents})  # Nova labels each doc with subjects; cached to subjects.json
    records = build_records(documents, tags)                      # chunk every doc + attach its metadata -> one record per chunk
    print(f"Built {len(records)} chunks. Embedding + indexing...")
    embed_records(records)                                        # add a Titan embedding vector to each chunk
    index_records(client, records)                                # bulk-load into OpenSearch, then wait until searchable


if __name__ == "__main__":
    main()
