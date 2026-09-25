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


def status(aoss) -> None:
    collection = get_collection(aoss)
    if not collection:
        print(f"Collection '{NAME}': does NOT exist.")
        return
    print(f"Collection '{NAME}': {collection['status']}")
    print(f"  endpoint: {collection.get('collectionEndpoint', '(pending)')}")
    logger.info("collection '%s' status=%s", NAME, collection["status"])
    if collection["status"] != "ACTIVE":
        return
    try:
        # Reuse client.py's own endpoint resolution + data-plane client rather
        # than re-implementing it here. Best-effort: a cold collection or a
        # transient data-plane error must not crash the status command.
        from client import INDEX_NAME, opensearch_client
        os_client = opensearch_client()
        if os_client.indices.exists(index=INDEX_NAME):
            count = os_client.count(index=INDEX_NAME)["count"]
            print(f"  index '{INDEX_NAME}': {count} chunks indexed")
            logger.debug("index '%s' chunk count=%d", INDEX_NAME, count)
        else:
            print(f"  index '{INDEX_NAME}': not created yet — run create_index.py")
    except Exception as exc:
        print(f"  (couldn't reach the data plane yet: {exc})")
        logger.warning("data plane not reachable yet for '%s': %s", NAME, exc)


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
