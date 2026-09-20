"""OpenSearch + Bedrock clients shared by this part's scripts.

Everything that talks to the managed store or the embedding model lives here, so
the scripts that build and query the index stay short. This is provided plumbing —
the OpenSearch + Bedrock wiring you build your filter+rerank pipeline on top of.
"""
import json
import os

import boto3
from dotenv import find_dotenv, load_dotenv
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

load_dotenv(find_dotenv())

REGION = os.environ.get("AWS_REGION", "us-east-1")
INDEX_NAME = "novaops-kb"       # the single index all of Lesson 7 shares
EMBED_DIM = 1024                # Titan V2 vector width
TOP_K = 4

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
EMBEDDING_MODEL_ID = os.environ.get("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")


def embed_text(text: str) -> list[float]:
    """One Titan embedding call — the same normalized 1024-dim vectors as Lesson 6.
    The index and the query must use the SAME model, or the vector geometry is
    meaningless."""
    resp = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": EMBED_DIM, "normalize": True}),
    )
    return json.loads(resp["body"].read())["embedding"]


def _aoss_session() -> boto3.Session:
    """The AWS session for OpenSearch Serverless — which may use DIFFERENT
    credentials than Bedrock. A student who can't get their own Bedrock access
    uses a SHARED Bedrock account (the default AWS_* keys) but owns their
    OpenSearch collection under their OWN account. If OPENSEARCH_AWS_* is set, sign
    aoss requests (both control- and data-plane) with those keys; otherwise fall
    back to the default session — the normal single-account case, unchanged."""
    key = os.environ.get("OPENSEARCH_AWS_ACCESS_KEY_ID")
    secret = os.environ.get("OPENSEARCH_AWS_SECRET_ACCESS_KEY")
    if key and secret:
        return boto3.Session(
            aws_access_key_id=key, aws_secret_access_key=secret, region_name=REGION
        )
    return boto3.Session(region_name=REGION)


def resolve_endpoint() -> str:
    """The collection's endpoint URL.

    We look it up by OPENSEARCH_COLLECTION via the control plane rather than
    hard-coding it — because deleting and recreating the collection (the optional
    teardown in manage.py, or a console recreate) yields a NEW endpoint. Resolving
    by name means that never needs a .env edit. (Set OPENSEARCH_ENDPOINT to override
    the lookup if you ever want to pin a specific endpoint.)"""
    override = os.environ.get("OPENSEARCH_ENDPOINT")
    if override:
        return override
    name = os.environ.get("OPENSEARCH_COLLECTION")
    if not name:
        raise SystemExit("Set OPENSEARCH_COLLECTION in .env to your OpenSearch collection's name.")
    aoss = _aoss_session().client("opensearchserverless")
    details = aoss.batch_get_collection(names=[name]).get("collectionDetails", [])
    if not details:
        raise SystemExit(
            f"Collection '{name}' not found — check the name and region, and that it's "
            "ACTIVE in the OpenSearch Serverless console."
        )
    endpoint = details[0].get("collectionEndpoint")
    if not endpoint:
        raise SystemExit(f"Collection '{name}' is {details[0].get('status')} — wait for ACTIVE.")
    return endpoint


def opensearch_client() -> OpenSearch:
    """Client for the OpenSearch Serverless collection, authenticated with SigV4.

    The service name is 'aoss' (OpenSearch Serverless); a managed OpenSearch
    *domain* would use 'es'. AWSV4SignerAuth signs every request with your AWS
    credentials — there is no username/password."""
    host = resolve_endpoint().replace("https://", "").replace("http://", "").rstrip("/")
    credentials = _aoss_session().get_credentials()
    auth = AWSV4SignerAuth(credentials, REGION, "aoss")
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
        # NextGen Serverless scales to zero when idle; the first request after an
        # idle period warms capacity up (~10 s), which overruns the default 10 s
        # timeout. Give it room and retry on timeout so a cold start doesn't fail.
        timeout=120,
        max_retries=3,
        retry_on_timeout=True,
    )
