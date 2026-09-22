"""Create the metadata index — non-destructive.

The mapping carries the vector field plus the three metadata fields the filters
in `retrieval.py` need, one per KIND of filter:
  - audience: 'all' or 'manager' — the ROLE-forced access filter (keyword).
  - subjects: the Nova-assigned topic labels — the LLM-planned subject filter
    (keyword; a keyword field transparently holds an ARRAY, so a chunk can carry
    several subjects).
  - last_updated: the document's date — the USER-supplied recency filter (date).

Keyword fields are exact-match (fast term/terms filters); the date field supports
range filters.

This script only ever CREATES a missing index. An index that already exists is
left exactly as it is — no delete, no recreate, no mapping change — because the
project's `novaops-kb` index is already populated and shared with the rest of
the pipeline. Deliberately destroying and recreating the collection/index is a
separate, explicit operation (manage.py), not something this script does as a
side effect of being run again.

    python create_index.py
"""
from client import EMBED_DIM, INDEX_NAME, opensearch_client

INDEX_BODY = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "vector": {
                "type": "knn_vector",
                "dimension": EMBED_DIM,
                # innerproduct on unit-normalized Titan vectors == cosine ranking.
                # NextGen picks/GPU-accelerates the engine itself (stored as faiss),
                # so we don't set an "engine" field.
                "method": {"name": "hnsw", "space_type": "innerproduct"},
            },
            "text": {"type": "text"},
            "source": {"type": "keyword"},
            "corpus": {"type": "keyword"},
            "audience": {"type": "keyword"},                          # role-forced access filter
            "subjects": {"type": "keyword"},                          # LLM-planned subject filter
            "last_updated": {"type": "date", "format": "yyyy-MM-dd"}, # user-supplied recency filter
        }
    },
}


def ensure_index(client) -> None:
    """Create INDEX_NAME if it's missing. If it already exists, report its
    document count and do nothing else — never delete, never recreate, never
    touch the mapping. Safe to run repeatedly against a populated index."""
    if client.indices.exists(index=INDEX_NAME):
        count = client.count(index=INDEX_NAME)["count"]
        print(f"Index '{INDEX_NAME}' already exists ({count} docs indexed) — left unchanged.")
        return
    client.indices.create(index=INDEX_NAME, body=INDEX_BODY)
    print(f"Created index '{INDEX_NAME}' (HNSW + audience + subjects + last_updated).")


def main() -> None:
    ensure_index(opensearch_client())


if __name__ == "__main__":
    main()
