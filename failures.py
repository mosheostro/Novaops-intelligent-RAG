"""Transport-independent failure categories for the application's use cases.

A transport adapter (the MCP server today, a REST API later) catches what a use
case such as ask.ask() or manage.collection_health() raises, asks
classify_failure() which category it belongs to, and then maps that category to
its own protocol — an MCP tool error, an HTTP status. This module knows nothing
about any transport, and the RAG core does not import it.

Only failures are categorized here. Business outcomes — not_found, a
role-filtered answer, a security-audit violation — are results, not exceptions,
and travel in the use case's return value. Invalid input is rejected by each
transport's own schema validation before a use case runs.

The classifier returns a category only, never the exception's message: messages
can carry infrastructure details (client.resolve_endpoint's SystemExit names the
collection), so what the caller is told is the adapter's own fixed wording.
"""
from typing import Literal

from botocore.exceptions import BotoCoreError, ClientError, ConnectTimeoutError, ReadTimeoutError
from opensearchpy.exceptions import ConnectionTimeout, OpenSearchException

from retrieval import UnsupportedAudienceError

FailureKind = Literal[
    "unsupported_role",
    "service_unavailable",
    "service_timeout",
    "internal",
]

# Every timeout subclasses one of the service bases below (ConnectionTimeout ->
# OpenSearchException; Read/ConnectTimeoutError -> BotoCoreError), so the
# timeout check must come first. opensearch-py reports read timeouts as
# ConnectionTimeout too.
_TIMEOUTS = (ConnectionTimeout, ReadTimeoutError, ConnectTimeoutError)
# SystemExit: client.resolve_endpoint exits when the collection is missing or not ACTIVE.
_SERVICE_FAILURES = (OpenSearchException, BotoCoreError, ClientError, SystemExit)


def classify_failure(exc: BaseException) -> FailureKind:
    """The category of a failure raised by a use case, most specific first.
    Anything not recognized is "internal": an adapter must then report it
    generically, without the exception's details."""
    if isinstance(exc, UnsupportedAudienceError):
        return "unsupported_role"
    if isinstance(exc, _TIMEOUTS):
        return "service_timeout"
    if isinstance(exc, _SERVICE_FAILURES):
        return "service_unavailable"
    return "internal"
