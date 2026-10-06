"""Inspect the OpenSearch Serverless collection — and optionally delete it.

This collection is NextGen Serverless, which scales its compute to zero after
~10 minutes idle: an idle collection costs almost nothing (only the stored
vectors, billed by the GB-month), so there is no per-session shutdown to do.
'status' is the everyday command — it's also a quick "is OpenSearch reachable?"
check.

'down' is a deliberate, destructive operation: it deletes the collection and
everything indexed in it. There is no 'up' and no automatic recreation — this
utility never creates or recreates the collection, and never touches policies.

    python manage.py status   # exists? Active? how many chunks?
    python manage.py down     # deliberately destructive: delete the collection
"""
import logging
import os
import sys
import time
from dataclasses import dataclass

import boto3

import config

logger = logging.getLogger(__name__)

REGION = config.AWS_REGION
NAME = config.OPENSEARCH_COLLECTION

CONFIRM_PHRASE = "REMOVE"


def _aoss_session() -> boto3.Session:
    """OpenSearch may use DIFFERENT credentials than Bedrock — mirrors the same
    helper in client.py. If OPENSEARCH_AWS_* is set, sign control-plane calls
    with those keys; otherwise fall back to the default session (the normal
    single-account case)."""
    key = os.environ.get("OPENSEARCH_AWS_ACCESS_KEY_ID")
    secret = os.environ.get("OPENSEARCH_AWS_SECRET_ACCESS_KEY")
    if key and secret:
        return boto3.Session(aws_access_key_id=key, aws_secret_access_key=secret, region_name=REGION)
    return boto3.Session(region_name=REGION)


def aoss_client():
    """The CONTROL-plane client for the collection itself (look up / delete) —
    distinct from client.py's DATA-plane client (index / search), which status()
    reuses below rather than duplicating its endpoint-resolution logic."""
    return _aoss_session().client("opensearchserverless")


def get_collection(aoss) -> dict | None:
    details = aoss.batch_get_collection(names=[NAME]).get("collectionDetails", [])
    return details[0] if details else None


@dataclass(frozen=True)
class CollectionHealth:
    """What `status` reports, as data. `status` is the collection's control-plane
    status ("ACTIVE", "CREATING", ...) or None when it does not exist.
    `index_exists` / `chunk_count` are None when the data plane was not checked
    (collection missing or not ACTIVE) or could not be reached; `data_plane_error`
    then says why. `endpoint` and `data_plane_error` are for the operator's CLI —
    callers outside this process decide for themselves what they may expose."""
    status: str | None
    endpoint: str | None
    index_exists: bool | None
    chunk_count: int | None
    data_plane_error: str | None


def collection_health(aoss) -> CollectionHealth:
    """Read-only health of the collection and its index. Prints nothing.
    Control-plane failures (credentials, access, network) propagate; the
    data-plane check is best-effort and records its failure instead."""
    collection = get_collection(aoss)
    if not collection:
        return CollectionHealth(status=None, endpoint=None, index_exists=None, chunk_count=None,
                                data_plane_error=None)
    state, endpoint = collection["status"], collection.get("collectionEndpoint")
    # Logs here carry states and exception types only — no collection or index name,
    # endpoint or exception text: they reach whoever runs this, e.g. an MCP client
    # reading the server's stderr.
    logger.info("collection status=%s", state)
    if state != "ACTIVE":
        return CollectionHealth(status=state, endpoint=endpoint, index_exists=None, chunk_count=None,
                                data_plane_error=None)
    try:
        # Reuse client.py's own endpoint resolution + data-plane client rather
        # than re-implementing it here. Best-effort: a cold collection or a
        # transient data-plane error must not crash the caller — including the
        # SystemExit client.resolve_endpoint raises for a missing/inactive collection.
        from client import INDEX_NAME, opensearch_client
        os_client = opensearch_client()
        if not os_client.indices.exists(index=INDEX_NAME):
            return CollectionHealth(status=state, endpoint=endpoint, index_exists=False, chunk_count=None,
                                    data_plane_error=None)
        count = os_client.count(index=INDEX_NAME)["count"]
        logger.debug("index chunk count=%d", count)
        return CollectionHealth(status=state, endpoint=endpoint, index_exists=True, chunk_count=count,
                                data_plane_error=None)
    except (Exception, SystemExit) as exc:
        logger.warning("data plane not reachable yet (%s)", type(exc).__name__)
        return CollectionHealth(status=state, endpoint=endpoint, index_exists=None, chunk_count=None,
                                data_plane_error=str(exc))


def status(aoss) -> None:
    health = collection_health(aoss)
    if health.status is None:
        print(f"Collection '{NAME}': does NOT exist.")
        return
    print(f"Collection '{NAME}': {health.status}")
    print(f"  endpoint: {'(pending)' if health.endpoint is None else health.endpoint}")
    if health.status != "ACTIVE":
        return
    if health.data_plane_error is not None:
        print(f"  (couldn't reach the data plane yet: {health.data_plane_error})")
        return
    from client import INDEX_NAME  # imported only now, as before: the data plane was reached
    if health.index_exists:
        print(f"  index '{INDEX_NAME}': {health.chunk_count} chunks indexed")
    else:
        print(f"  index '{INDEX_NAME}': not created yet — run create_index.py")


def down(aoss) -> None:
    """Deliberately destructive. Confirmation happens BEFORE the delete call:
    only the exact string "REMOVE" authorizes it; anything else — including no
    input, "y", "yes", or a differently-cased "remove" — cancels. There is no
    --force flag or other bypass."""
    collection = get_collection(aoss)
    if not collection:
        print(f"Collection '{NAME}' already gone — nothing to delete.")
        return
    print(f"This will PERMANENTLY DELETE collection '{NAME}' and all of its stored vector data.")
    answer = input(f"Type {CONFIRM_PHRASE} to confirm, or anything else to cancel: ")
    if answer != CONFIRM_PHRASE:
        print("Cancelled — collection left untouched.")
        logger.info("delete cancelled for collection '%s'", NAME)
        return
    logger.warning("delete confirmed for collection '%s' (id=%s); proceeding", NAME, collection["id"])
    aoss.delete_collection(id=collection["id"])
    print(f"Deleting collection '{NAME}' (id {collection['id']}).")
    for _ in range(30):
        if get_collection(aoss) is None:
            print("Done — collection deleted.")
            logger.info("collection '%s' deleted", NAME)
            return
        time.sleep(5)
    print("Delete requested — still finalizing; it will disappear shortly.")
    logger.info("collection '%s' delete requested, still finalizing", NAME)


COMMANDS = {"status": status, "down": down}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in COMMANDS:
        raise SystemExit("usage: python manage.py [status|down]")
    COMMANDS[cmd](aoss_client())


if __name__ == "__main__":
    main()
