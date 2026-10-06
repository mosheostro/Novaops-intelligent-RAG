"""failures.py — transport-independent failure classification. Real exception
classes from retrieval, opensearch-py and botocore are constructed directly;
nothing is raised by a network call. No AWS, OpenSearch, Bedrock or MCP."""
import ast
import os
import unittest
from pathlib import Path
from typing import get_args

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from botocore.exceptions import (  # noqa: E402
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    ReadTimeoutError,
)
from opensearchpy.exceptions import (  # noqa: E402
    ConnectionError as OpenSearchConnectionError,
    ConnectionTimeout,
    OpenSearchException,
    TransportError,
)

from failures import FailureKind, classify_failure  # noqa: E402
from retrieval import UnsupportedAudienceError  # noqa: E402

ENDPOINT = "https://example.invalid"
OPENSEARCH_TIMEOUT = ConnectionTimeout("TIMEOUT", "Read timed out", Exception())
BEDROCK_READ_TIMEOUT = ReadTimeoutError(endpoint_url=ENDPOINT)
BEDROCK_CONNECT_TIMEOUT = ConnectTimeoutError(endpoint_url=ENDPOINT)
ACCESS_DENIED = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "Converse")


class ClassifyFailureTests(unittest.TestCase):
    def assertKind(self, exc: BaseException, kind: str):
        self.assertEqual(classify_failure(exc), kind, type(exc).__name__)

    def test_unsupported_audience_is_unsupported_role(self):
        # A ValueError subclass — must not fall through to "internal".
        self.assertKind(UnsupportedAudienceError("Unsupported audience 'boss'"), "unsupported_role")

    def test_opensearch_timeout_is_service_timeout(self):
        self.assertKind(OPENSEARCH_TIMEOUT, "service_timeout")

    def test_botocore_read_and_connect_timeouts_are_service_timeout(self):
        self.assertKind(BEDROCK_READ_TIMEOUT, "service_timeout")
        self.assertKind(BEDROCK_CONNECT_TIMEOUT, "service_timeout")

    def test_timeouts_win_over_their_broader_service_base_classes(self):
        # The hierarchy that makes the ordering matter, asserted rather than assumed.
        self.assertIsInstance(OPENSEARCH_TIMEOUT, OpenSearchException)
        self.assertIsInstance(BEDROCK_READ_TIMEOUT, BotoCoreError)
        self.assertIsInstance(BEDROCK_CONNECT_TIMEOUT, BotoCoreError)
        for exc in (OPENSEARCH_TIMEOUT, BEDROCK_READ_TIMEOUT, BEDROCK_CONNECT_TIMEOUT):
            self.assertKind(exc, "service_timeout")

    def test_opensearch_service_errors_are_service_unavailable(self):
        for exc in (OpenSearchException("boom"), TransportError(503, "unavailable"),
                    OpenSearchConnectionError("N/A", "connection refused", Exception())):
            self.assertKind(exc, "service_unavailable")

    def test_botocore_errors_are_service_unavailable(self):
        for exc in (BotoCoreError(), NoCredentialsError(), EndpointConnectionError(endpoint_url=ENDPOINT)):
            self.assertKind(exc, "service_unavailable")

    def test_client_error_is_service_unavailable(self):
        self.assertKind(ACCESS_DENIED, "service_unavailable")

    def test_system_exit_is_service_unavailable(self):
        # client.resolve_endpoint signals a missing/inactive collection with SystemExit.
        self.assertKind(SystemExit("Collection 'x' not found"), "service_unavailable")

    def test_everything_else_is_internal(self):
        for exc in (ValueError("bad"), RuntimeError("unexpected"), KeyError("k"), TypeError("t")):
            self.assertKind(exc, "internal")

    def test_result_is_always_a_category_never_the_message(self):
        secret = "SECRET-COLLECTION https://abc.aoss.amazonaws.com"
        for exc in (SystemExit(secret), RuntimeError(secret), OpenSearchException(secret)):
            kind = classify_failure(exc)
            self.assertIn(kind, get_args(FailureKind))
            self.assertNotIn("SECRET", kind)


class FailuresModuleBoundaryTests(unittest.TestCase):
    def test_depends_on_no_transport_or_ui(self):
        tree = ast.parse((Path(__file__).resolve().parent.parent / "failures.py").read_text(encoding="utf-8"))
        imported = {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
        imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        roots = {name.split(".")[0] for name in imported}
        self.assertFalse(roots & {"mcp", "mcp_server", "streamlit", "ui", "fastapi", "starlette"})


if __name__ == "__main__":
    unittest.main()
