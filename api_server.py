"""REST API for the NovaOps knowledge base — a thin HTTP adapter over the existing
application use cases, independent of the MCP adapter. It owns routes, request
schemas, the HTTP boundary and the problem+json error contract, and nothing else:
retrieval, access control, reranking, auditing and judging stay in the core, and
what leaves the process is the shared public views in public_views.py.

    python api_server.py --role employee [--host 127.0.0.1] [--port 8001]

The role is a SERVER role, fixed at startup and validated by retrieval's own
access_filter() — no default, never taken from a request. It is not
authentication: whoever starts the process chooses it.

There is no authentication, so the server binds to loopback only and guards the
HTTP boundary itself:
  - Host allow-list: only loopback names, which defeats DNS rebinding;
  - request bodies must be declared application/json (a missing Content-Type is
    refused too), so a browser cannot send one cross-site without a CORS
    preflight — and there is no CORS, so the preflight fails.
Every error is an RFC 9457 problem (application/problem+json) with fixed wording:
never the request's input, never an exception's message.
"""
import argparse
import logging
import re
import threading
from collections.abc import Callable, Sequence
from datetime import date
from http import HTTPStatus
from typing import Annotated, TypeVar

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, Strict, StrictBool
from starlette.exceptions import HTTPException as StarletteHTTPException

import config  # noqa: F401  -- validates the environment before any project module is imported

import ask
import client
import manage
from failures import FailureKind, classify_failure
from logging_setup import NOISY_THIRD_PARTY_LOGGERS
from models import DEFAULT_CONFIG, ConfigName
from public_views import (
    MAX_QUESTION_CHARS,
    AskRagResult,
    ConfigurationCapability,
    HealthResult,
    Question,
    configuration_capabilities,
    project_ask_result,
    project_health,
)
from retrieval import SUPPORTED_AUDIENCES, UnsupportedAudienceError, access_filter
from subjects import SUBJECTS

logger = logging.getLogger(__name__)

# The same neutral public name the MCP server announces; never an infrastructure identifier.
SERVICE_NAME = "novaops-knowledge-base"
# This REST server implementation's version, bumped by hand. Independent of the MCP server's.
API_SERVER_VERSION = "0.1.0"
API_VERSION = "v1"  # the path prefix; a breaking contract change gets a new one
DEFAULT_PORT = 8001
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
# The same hosts as they appear in a Host header (an IPv6 literal is bracketed there).
_HOST_HEADER_NAMES = ("127.0.0.1", "localhost", "[::1]")
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

PROBLEM_MEDIA_TYPE = "application/problem+json"
# Every problem this API returns: code -> (status, title, fixed detail).
_PROBLEMS: dict[str, tuple[int, str, str]] = {
    "invalid-host": (400, "Invalid Host header",
                     "The Host header must name a loopback address: this API serves local clients only."),
    "not-found": (404, "Not found", "No resource exists at this path."),
    "method-not-allowed": (405, "Method not allowed",
                           "The resource does not support this method; see the Allow header."),
    "unsupported-media-type": (415, "Unsupported media type",
                               "Request bodies must be JSON, sent with Content-Type: application/json."),
    "validation-error": (422, "Invalid request", "The request does not match the expected schema; see errors."),
    "server-misconfigured": (500, "Server misconfigured", "The server's configured role is not supported."),
    "internal-error": (500, "Internal error", "The request could not be completed. Details are in the server log."),
    "service-unavailable": (503, "Service unavailable",
                            "The knowledge base or model service is unavailable. Try again later."),
    "service-timeout": (504, "Service timeout",
                        "The knowledge base did not respond in time; it may be warming up. Retry shortly."),
}
_FAILURE_PROBLEMS: dict[FailureKind, str] = {
    "unsupported_role": "server-misconfigured",  # the role is validated at startup, so this is a server fault
    "service_unavailable": "service-unavailable",
    "service_timeout": "service-timeout",
}

T = TypeVar("T")

_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _iso_date_only(value):
    """Only the exact YYYY-MM-DD form reaches date parsing — no timestamps, datetimes
    or compact forms, which lax date parsing would otherwise accept."""
    if value is not None and not (isinstance(value, str) and _ISO_DATE.fullmatch(value)):
        raise ValueError("must be an ISO date, YYYY-MM-DD")
    return value


class AskRequest(BaseModel):
    """The POST /v1/ask body. There is no role: the server's role is fixed at startup."""
    model_config = ConfigDict(extra="forbid")

    question: Annotated[Question, Strict()]
    config: ConfigName = DEFAULT_CONFIG
    judge: StrictBool = Field(False, description="Add LLM quality scores (3-4 more model calls, slower).")
    updated_on_or_after: Annotated[date | None, BeforeValidator(_iso_date_only), Field(
        description="Optional ISO date, YYYY-MM-DD. Keeps only documents updated on or after it; "
                    "narrows retrieval, never widens access.")] = None


class ProblemFieldError(BaseModel):
    location: list[str]
    message: str
    type: str


class Problem(BaseModel):
    """RFC 9457 problem details — the shape of every error this API returns."""
    type: str
    title: str
    status: int
    detail: str
    errors: list[ProblemFieldError] | None = Field(None, description="Validation errors only.")


class ApiInfo(BaseModel):
    """Who this server is. The role is the only per-server value."""
    name: str
    version: str
    api_version: str
    role: str


class JudgingCapability(BaseModel):
    field: str
    default: bool
    judges: list[str]
    note: str


class SecurityCapability(BaseModel):
    role: str
    access_filter: str
    security_audit: str


class RequestLimits(BaseModel):
    question_max_chars: int
    updated_on_or_after_format: str


class ApiCapabilities(BaseModel):
    """What a request can ask for and how answers behave — semantics only, never
    infrastructure or tuning values. The same for every role."""
    configurations: list[ConfigurationCapability]
    default_configuration: ConfigName
    judging: JudgingCapability
    security: SecurityCapability
    limits: RequestLimits


class SubjectList(BaseModel):
    """The fixed subject vocabulary the planner and the subject filter use. Informational:
    requests do not pass subjects; the planner chooses them from the question."""
    subjects: list[str]


_CAPABILITIES = ApiCapabilities(
    configurations=configuration_capabilities(),
    default_configuration=DEFAULT_CONFIG,
    judging=JudgingCapability(
        field="judge", default=False,
        judges=["faithfulness", "context_relevance", "context_completeness", "refusal"],
        note="Adds 3-4 model calls. context_completeness is skipped when no context is selected or the answer "
             "is a refusal. The judgement is withheld when the security audit fails.",
    ),
    security=SecurityCapability(
        role="The server's role is fixed at startup and selects the audience filter for every request. "
             "It is not authentication, and a request cannot choose it.",
        access_filter="Always applied from the server's role; an unsupported role is rejected (fail closed).",
        security_audit="Every answer includes security_audit. If retrieval returns content outside the role's "
                       "permitted audience, the answer, sources and judgement are withheld: still an HTTP 200 "
                       "result, not an error.",
    ),
    limits=RequestLimits(question_max_chars=MAX_QUESTION_CHARS, updated_on_or_after_format="YYYY-MM-DD"),
)
_SUBJECTS = SubjectList(subjects=list(SUBJECTS))


def _problem_responses(*statuses: int) -> dict[int, dict]:
    return {status: {"description": HTTPStatus(status).phrase,
                     "content": {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/Problem"}}}}
            for status in statuses}


def _lazy_opensearch() -> Callable[[], object]:
    """The OpenSearch client, created on first use so the server starts (and
    liveness answers) while the collection is unreachable. Cached only after a
    successful creation; locked, because sync routes run on worker threads."""
    lock = threading.Lock()
    created = []

    def get():
        with lock:
            if not created:
                created.append(client.opensearch_client())
            return created[0]
    return get


def problem(code: str, headers: dict[str, str] | None = None, **extensions) -> JSONResponse:
    status, title, detail = _PROBLEMS[code]
    return JSONResponse(
        {"type": f"urn:novaops:problem:{code}", "title": title, "status": status, "detail": detail, **extensions},
        status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers,
    )


class ServiceFailure(Exception):
    """A use case failed for a known reason (a failures.py category other than
    "internal"). Carries the category only — never the original message."""

    def __init__(self, kind: FailureKind):
        super().__init__(kind)
        self.kind = kind


def run_use_case(operation: str, use_case: Callable[[], T]) -> T:
    """Run a use case and translate its failure into this transport's terms.
    SystemExit is caught too: client.resolve_endpoint exits when the collection is
    missing or not ACTIVE, which must fail one request, not end the server. Known
    categories become a ServiceFailure; anything else is re-raised and reported as
    a generic internal error (traceback to the server log only)."""
    try:
        return use_case()
    except (Exception, SystemExit) as exc:
        kind = classify_failure(exc)
        if kind == "internal":
            raise
        logger.warning("%s failed: %s (%s)", operation, kind, type(exc).__name__)
        raise ServiceFailure(kind) from None


def _is_loopback_host(header: str) -> bool:
    host = header.strip().lower()
    return any(host == name or (host.startswith(name + ":") and host[len(name) + 1:].isdigit())
               for name in _HOST_HEADER_NAMES)


def _is_json(content_type: str) -> bool:
    return content_type.split(";", 1)[0].strip().lower() == "application/json"


async def _http_boundary(request: Request, call_next):
    if not _is_loopback_host(request.headers.get("host", "")):
        return problem("invalid-host")
    if request.method in _BODY_METHODS and not _is_json(request.headers.get("content-type", "")):
        return problem("unsupported-media-type")
    return await call_next(request)


async def _validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Which fields failed and why — never the submitted values. An unknown field is
    located by its name, e.g. ["body", "role"], so a caller sees what was rejected."""
    errors = [{"location": [str(part) for part in error.get("loc", ())], "message": error.get("msg", ""),
               "type": error.get("type", "")}
              for error in exc.errors()]
    return problem("validation-error", errors=errors)


async def _http_problem(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {404: "not-found", 405: "method-not-allowed", 415: "unsupported-media-type"}.get(exc.status_code)
    if code:
        return problem(code, headers=exc.headers)
    # Any other HTTP error raised by the framework keeps its status; its detail is not repeated.
    status = HTTPStatus(exc.status_code)
    return JSONResponse({"type": "urn:novaops:problem:http-error", "title": status.phrase, "status": status.value,
                         "detail": status.description or status.phrase},
                        status_code=status.value, media_type=PROBLEM_MEDIA_TYPE, headers=exc.headers)


async def _service_problem(request: Request, exc: ServiceFailure) -> JSONResponse:
    return problem(_FAILURE_PROBLEMS[exc.kind])


async def _internal_problem(request: Request, exc: Exception) -> JSONResponse:
    return problem("internal-error")


def build_app(role: str) -> FastAPI:
    """The REST app for one configured role. The role is validated first, so an
    app with an unsupported role is never constructed."""
    access_filter(role)  # the single source of truth for supported roles; raises UnsupportedAudienceError
    app = FastAPI(title=SERVICE_NAME, version=API_SERVER_VERSION,
                  description="NovaOps knowledge base REST API — loopback only, role fixed at startup.")
    app.middleware("http")(_http_boundary)
    app.add_exception_handler(RequestValidationError, _validation_problem)
    app.add_exception_handler(StarletteHTTPException, _http_problem)
    app.add_exception_handler(ServiceFailure, _service_problem)
    app.add_exception_handler(Exception, _internal_problem)
    opensearch = _lazy_opensearch()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness: the process is up and serving. No knowledge-base or model call."""
        return {"status": "ok"}

    @app.post("/v1/ask", response_model=AskRagResult, responses=_problem_responses(415, 422, 500, 503, 504))
    def ask_question(body: AskRequest) -> AskRagResult:
        """Answer a question from the NovaOps knowledge base as the role this server was started
        with. `not_found` and a failed security audit (answer withheld) are normal 200 results.
        A first call after an idle period can take a while as the knowledge base warms up."""
        result = run_use_case("ask", lambda: ask.ask(opensearch(), body.question, role, body.config,
                                                     judge=body.judge, cutoff=body.updated_on_or_after))
        return project_ask_result(result)

    @app.get("/v1/health", response_model=HealthResult, responses={
        503: {"description": "Not ready (a HealthResult), or the knowledge base could not be checked (a problem)",
              "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HealthResult"}},
                          PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/Problem"}}}},
        **_problem_responses(500, 504)})
    def health(response: Response) -> HealthResult:
        """Readiness of the knowledge base: collection state, index presence and chunk count.
        200 when ready, 503 with the same body when not. Read-only; a call after an idle
        period also warms the knowledge base up. For process liveness use /healthz."""
        result = project_health(run_use_case("health", lambda: manage.collection_health(manage.aoss_client())))
        response.status_code = 200 if result.ready else 503
        return result

    info_result = ApiInfo(name=SERVICE_NAME, version=API_SERVER_VERSION, api_version=API_VERSION, role=role)

    @app.get("/v1/info")
    def info() -> ApiInfo:
        """This server's name, implementation version, API version and fixed role. No backend call."""
        return info_result

    @app.get("/v1/capabilities")
    def capabilities() -> ApiCapabilities:
        """The answer configurations and their behavior, the default, judging, security behavior
        and request limits. The same for every role. No backend call."""
        return _CAPABILITIES

    @app.get("/v1/subjects")
    def subjects() -> SubjectList:
        """The subject vocabulary used to plan and filter retrieval. No backend call."""
        return _SUBJECTS

    def openapi() -> dict:
        # Errors are documented as problem+json, not as FastAPI's default validation-error schema.
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, description=app.description,
                                 routes=app.routes)
            schemas = schema.setdefault("components", {}).setdefault("schemas", {})
            for name in ("HTTPValidationError", "ValidationError"):
                schemas.pop(name, None)
            problem_schema = Problem.model_json_schema(ref_template="#/components/schemas/{model}")
            schemas.update(problem_schema.pop("$defs", {}))
            schemas["Problem"] = problem_schema
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    return app


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="NovaOps knowledge base REST API (loopback only).")
    parser.add_argument("--role", required=True,
                        help=f"server role, one of {sorted(SUPPORTED_AUDIENCES)}; not authentication")
    parser.add_argument("--host", default="127.0.0.1", help=f"loopback only, one of {list(LOOPBACK_HOSTS)}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if args.host not in LOOPBACK_HOSTS:
        parser.error(f"--host must be a loopback address, one of {list(LOOPBACK_HOSTS)}: "
                     "the REST API has no authentication")
    try:
        app = build_app(args.role)
    except UnsupportedAudienceError:
        parser.error(f"unsupported role {args.role!r}; expected one of {sorted(SUPPORTED_AUDIENCES)}")
    for name in NOISY_THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    uvicorn.run(app, host=args.host, port=args.port)  # an app object: one process, no reload, no workers


if __name__ == "__main__":
    main()
