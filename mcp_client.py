"""Demo MCP client for the NovaOps knowledge-base server — STDIO or Streamable HTTP.

One command per run, each a single MCP interaction:

    python mcp_client.py discover --url http://127.0.0.1:8000/mcp     # identity, tools, resources,
                                                                      # capabilities, subjects (no AWS)
    python mcp_client.py health   --url http://127.0.0.1:8000/mcp     # health_check tool
    python mcp_client.py ask "How does PTO accrue?" --url http://127.0.0.1:8000/mcp [--config NAME]
                         [--judge] [--updated-on-or-after YYYY-MM-DD]  # ask_rag tool
    python mcp_client.py discover --role manager                       # STDIO instead of HTTP

--url connects to an already running server and never starts one (its role is
whatever it was started with). --role starts a STDIO server with that role for
this one command. Text output by default; --json prints exactly what the server
returned.

describe() / check_health() / ask() are a small synchronous facade over HTTP for
callers that are not async (the dashboard's MCP page): plain values in, plain
dicts out, MCP and anyio details stay in this module.

Deliberately thin: the server is the source of truth. This client validates no
role, retrieves nothing, filters nothing and classifies no failure — it passes
the role through, prints what the server returns, and surfaces a tool error with
the server's own (already safe) message. It imports nothing from the RAG core or
from mcp_server. `health_check` and `ask_rag` make live AWS calls on the server.
"""
import argparse
import json
import re
import sys
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal, TextIO, TypeVar
from urllib.parse import SplitResult, urlsplit

import anyio
import httpx2
from mcp import ClientSession, MCPError, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CONNECTION_CLOSED, METHOD_NOT_FOUND

PROJECT_ROOT = Path(__file__).resolve().parent
SUBJECTS_URI = "rag://subjects"
MCP_ENDPOINT = "/mcp"  # the NovaOps server's fixed Streamable HTTP path
EXAMPLE_URL = "http://127.0.0.1:8000/mcp"
CONNECT_TIMEOUT = 30.0  # seconds; the SDK's own default, kept when only the read timeout is shortened

T = TypeVar("T")
UnavailableKind = Literal["unreachable", "timeout", "not_found", "not_mcp", "dropped"]


class ToolCallError(RuntimeError):
    """The server answered a tool call with an error; the message is the server's own."""


class InvalidServerUrlError(ValueError):
    """The server URL is malformed; the message says how to fix it. Raised before any connection."""


class ServerUnavailableError(RuntimeError):
    """Connection, protocol or timeout failure talking to an HTTP server. `kind` says which;
    the message is fixed wording plus the URL's scheme, host, port and path — never the
    underlying exception's text, nor the URL's credentials or query."""

    def __init__(self, kind: UnavailableKind, message: str):
        super().__init__(message)
        self.kind = kind


def check_url(url: str) -> None:
    """Raise InvalidServerUrlError unless `url` looks like http(s)://host[:port]/path."""
    def invalid(reason: str) -> InvalidServerUrlError:
        return InvalidServerUrlError(f"invalid MCP server URL {url!r}: {reason}")

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        if "://" in url:
            raise invalid("only http:// and https:// are supported")
        suggestion = EXAMPLE_URL if not url else f"http://{url}" if "/" in url else f"http://{url}{MCP_ENDPOINT}"
        raise invalid(f"it must start with http://, e.g. {suggestion}")
    if not parts.hostname:
        raise invalid(f"the host is missing, e.g. {EXAMPLE_URL}")
    try:
        parts.port
    except ValueError:
        raise invalid("the port must be a number") from None
    if parts.path in ("", "/"):
        raise invalid(f"the endpoint path is missing; the NovaOps MCP endpoint is {MCP_ENDPOINT}, "
                      f"e.g. {_origin(parts)}{MCP_ENDPOINT}")


def _host_port(parts: SplitResult) -> str:
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    return f"{host}:{parts.port}" if parts.port else host


def _origin(parts: SplitResult) -> str:
    return f"{parts.scheme}://{_host_port(parts)}"


def _unavailable(exc: Exception, url: str) -> ServerUnavailableError:
    """A transport failure as a safe, actionable error. Only the caller's own URL is echoed,
    without credentials or query; the exception's text never is (it can carry server output)."""
    parts = urlsplit(url)
    where, host_port = f"{_origin(parts)}{parts.path}", _host_port(parts)
    if isinstance(exc, httpx2.TimeoutException):
        return ServerUnavailableError("timeout", f"the MCP server at {where} did not respond in time")
    if isinstance(exc, httpx2.ConnectError):
        hint = (f"The NovaOps MCP server speaks plain http; try http://{host_port}{parts.path}"
                if parts.scheme == "https" else
                "Is the MCP server running? Start it with: python mcp_server.py --transport streamable-http "
                f"--role employee --port {parts.port or 80}")
        return ServerUnavailableError(
            "unreachable", f"could not connect to {host_port} (connection refused or unknown host). {hint}")
    if isinstance(exc, (httpx2.RemoteProtocolError, httpx2.ReadError, httpx2.WriteError)) or (
            isinstance(exc, MCPError) and exc.code == CONNECTION_CLOSED):
        return ServerUnavailableError("dropped", f"the connection to {where} was closed unexpectedly")
    if isinstance(exc, MCPError) and exc.code == METHOD_NOT_FOUND and exc.message == "Not Found":  # SDK: HTTP 404
        return ServerUnavailableError(
            "not_found", f"{host_port} answered, but there is no MCP endpoint at {parts.path!r} (HTTP 404); "
                         f"the NovaOps MCP endpoint is {MCP_ENDPOINT}, e.g. {_origin(parts)}{MCP_ENDPOINT}")
    return ServerUnavailableError("not_mcp", f"{where} answered, but not as an MCP server")


def server_parameters(role: str, env: dict[str, str] | None = None) -> StdioServerParameters:
    """How to launch the server. `role` is passed through unchecked — the server
    validates it and refuses to start on an unsupported one. `env` is merged over
    the SDK's minimal inherited environment; the server reads its own .env."""
    return StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server", "--role", role], cwd=PROJECT_ROOT, env=env,
    )


@asynccontextmanager
async def connect(role: str, env: dict[str, str] | None = None,
                  errlog: TextIO | None = None) -> AsyncIterator[ClientSession]:
    """An initialized session with a freshly started server; the server stops on exit.
    `errlog` receives the server's stderr (it must be a real file: the SDK hands it
    to the subprocess as its stderr); default: this process's stderr."""
    async with stdio_client(server_parameters(role, env), errlog=errlog or sys.stderr) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def connect_http(url: str, read_timeout: float | None = None) -> AsyncIterator[ClientSession]:
    """An initialized session with an already running Streamable HTTP server. By default
    the SDK's own HTTP client and timeouts apply (a 300 s read timeout); `read_timeout`
    (seconds) replaces only the read timeout, for this connection only."""
    async with AsyncExitStack() as stack:
        http_client = None
        if read_timeout is not None:
            http_client = await stack.enter_async_context(
                httpx2.AsyncClient(timeout=httpx2.Timeout(CONNECT_TIMEOUT, read=read_timeout)))
        read, write = await stack.enter_async_context(streamable_http_client(url, http_client=http_client))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        yield session


async def call_tool(session: ClientSession, name: str, arguments: dict | None = None) -> dict:
    result = await session.call_tool(name, arguments or {})
    if result.is_error:
        raise ToolCallError(result.content[0].text if result.content else f"{name} failed")
    return result.structured_content


async def read_json_resource(session: ClientSession, uri: str) -> dict:
    result = await session.read_resource(uri)
    return json.loads(result.contents[0].text)


async def discover(session: ClientSession) -> dict:
    """The static surface: no AWS or OpenSearch call on the server."""
    tools = await session.list_tools()
    resources = await session.list_resources()
    return {
        "tools": sorted(t.name for t in tools.tools),
        "resources": sorted(str(r.uri) for r in resources.resources),
        "capabilities": await call_tool(session, "get_rag_capabilities"),
        "subjects": (await read_json_resource(session, SUBJECTS_URI))["subjects"],
    }


async def describe_session(session: ClientSession, transport: str) -> dict:
    """Server identity and transport plus the static surface. No AWS call."""
    server = session.server_info  # set by the handshake; optional in the protocol
    return {"server": {"name": server.name if server else None, "version": server.version if server else None},
            "transport": transport, **await discover(session)}


async def published_descriptions(session: ClientSession) -> dict[str, str]:
    """The descriptions the server publishes, keyed by tool name and by resource URI."""
    tools, resources = await session.list_tools(), await session.list_resources()
    return {**{t.name: t.description or "" for t in tools.tools},
            **{str(r.uri): r.description or "" for r in resources.resources}}


def ask_arguments(question: str, config: str | None = None, judge: bool = False,
                  updated_on_or_after: date | None = None) -> dict:
    """ask_rag's arguments. Omitted options are not sent, so the server's defaults apply."""
    arguments: dict = {"question": question, "judge": judge}
    if config is not None:
        arguments["config"] = config
    if updated_on_or_after is not None:
        arguments["updated_on_or_after"] = updated_on_or_after.isoformat()
    return arguments


def _over_http(url: str, action: Callable[[ClientSession], Awaitable[T]], read_timeout: float | None = None) -> T:
    """Run one action in its own short HTTP session, synchronously. Raises InvalidServerUrlError,
    ToolCallError or ServerUnavailableError as plain exceptions, never as an ExceptionGroup."""
    check_url(url)

    async def run() -> T | ToolCallError:
        async with connect_http(url, read_timeout=read_timeout) as session:
            # Caught inside the session: an exception leaving the SDK's task group
            # arrives wrapped in an ExceptionGroup.
            try:
                return await action(session)
            except ToolCallError as exc:
                return exc

    failure = None
    try:
        result = anyio.run(run)
    except* (MCPError, httpx2.HTTPError) as group:  # refused, timed out, dropped, or not an MCP endpoint
        cause = group
        while isinstance(cause, BaseExceptionGroup):  # the SDK's task groups nest the error
            cause = cause.exceptions[0]
        failure = _unavailable(cause, url)
    if failure:  # raised out here: inside except* it would be wrapped in a new ExceptionGroup
        raise failure
    if isinstance(result, ToolCallError):
        raise result
    return result


def describe(url: str, read_timeout: float | None = None) -> dict:
    """Server identity, transport, tools, resources, capabilities and subjects. No AWS call."""
    return _over_http(url, lambda session: describe_session(session, "streamable-http"), read_timeout)


def check_health(url: str, read_timeout: float | None = None) -> dict:
    return _over_http(url, lambda session: call_tool(session, "health_check"), read_timeout)


def ask(url: str, question: str, config: str | None = None, judge: bool = False,
        updated_on_or_after: date | None = None, read_timeout: float | None = None) -> dict:
    """One ask_rag call. Omitted options are not sent, so the server's defaults apply."""
    arguments = ask_arguments(question, config, judge, updated_on_or_after)
    return _over_http(url, lambda session: call_tool(session, "ask_rag", arguments), read_timeout)


# --- Command line ---------------------------------------------------------------------------------

def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an ISO date YYYY-MM-DD (e.g. 2025-01-31), got {value!r}") from None


def _parser() -> argparse.ArgumentParser:
    target = argparse.ArgumentParser(add_help=False)
    where = target.add_argument_group("server (exactly one)").add_mutually_exclusive_group(required=True)
    where.add_argument("--url", help=f"Streamable HTTP: a running server's endpoint, e.g. {EXAMPLE_URL}")
    where.add_argument("--role", help="STDIO: start a server with this role for this one command "
                                      "(passed through; the server validates it)")
    target.add_argument("--json", action="store_true", help="print the MCP result as JSON instead of text")

    parser = argparse.ArgumentParser(
        prog="mcp_client.py", description="Demo MCP client for the NovaOps knowledge-base server.",
        epilog=f"examples:\n  python mcp_client.py discover --url {EXAMPLE_URL}\n"
               f"  python mcp_client.py health --url {EXAMPLE_URL}\n"
               f"  python mcp_client.py ask \"How does PTO accrue?\" --url {EXAMPLE_URL}\n"
               "  python mcp_client.py discover --role employee",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser("discover", parents=[target],
                        help="server identity, tools, resources, capabilities and subjects (no AWS call)")
    commands.add_parser("health", parents=[target], help="the health_check tool (a read-only AWS status check)")
    ask_command = commands.add_parser("ask", parents=[target], help="the ask_rag tool (calls AWS Bedrock)")
    ask_command.add_argument("question")
    ask_command.add_argument("--config", help="a configuration name from discover; default: the server's")
    ask_command.add_argument("--judge", action="store_true", help="also score the answer (extra model calls)")
    ask_command.add_argument("--updated-on-or-after", type=_iso_date, metavar="YYYY-MM-DD",
                             help="only documents updated on or after this date")
    return parser


def _action(args: argparse.Namespace) -> Callable[[ClientSession], Awaitable[dict]]:
    if args.command == "discover":
        transport = "streamable-http" if args.url else "stdio"
        if args.json:  # exactly describe()'s result
            return lambda session: describe_session(session, transport)

        async def with_descriptions(session: ClientSession) -> dict:  # the text view also shows descriptions
            return {**await describe_session(session, transport),
                    "descriptions": await published_descriptions(session)}
        return with_descriptions
    if args.command == "health":
        return lambda session: call_tool(session, "health_check")
    arguments = ask_arguments(args.question, args.config, args.judge, args.updated_on_or_after)
    return lambda session: call_tool(session, "ask_rag", arguments)


def main(argv: Sequence[str] | None = None) -> None:
    parser = _parser()
    args = parser.parse_args(argv)
    action = _action(args)

    if args.url:
        try:
            check_url(args.url)
        except InvalidServerUrlError as exc:
            parser.error(str(exc))
        try:
            result = _over_http(args.url, action)
        except ServerUnavailableError as exc:
            parser.exit(1, f"error: {exc}\n")
        except ToolCallError as exc:
            parser.exit(1, f"tool error: {exc}\n")
    else:
        result = _over_stdio(parser, args.role, action)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else _FORMATTERS[args.command](result))


def _over_stdio(parser: argparse.ArgumentParser, role: str, action: Callable[[ClientSession], Awaitable[dict]]) -> dict:
    """Run one action against a freshly started STDIO server; exit with a one-line reason on failure."""
    # The server's stderr is captured rather than inherited: on a Windows console the
    # server runs without a console of its own, so its messages would otherwise be lost.
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as server_log:
        async def run() -> dict | ToolCallError:
            async with connect(role, env={"PYTHONIOENCODING": "utf-8"}, errlog=server_log) as session:
                # Caught inside the session: an exception leaving the SDK's task group
                # arrives wrapped in an ExceptionGroup.
                try:
                    return await action(session)
                except ToolCallError as exc:
                    return exc

        try:
            result = anyio.run(run)
        except* MCPError as group:
            # The session itself failed — typically the server refused to start (e.g. an
            # unsupported role) and exited before the handshake.
            result = group
            while isinstance(result, BaseExceptionGroup):  # the SDK's task groups nest the error
                result = result.exceptions[0]
        server_log.seek(0)
        server_output = server_log.read()

    if isinstance(result, MCPError):
        parser.exit(1, f"error: {_server_failure(server_output, result)}\n")
    sys.stderr.write(server_output)  # the server's own (sanitized) operational log
    if isinstance(result, ToolCallError):
        parser.exit(1, f"tool error: {result}\n")
    return result


def _server_failure(server_output: str, error: MCPError) -> str:
    """One line saying why the server went away: its own last error line (argparse's
    "prog: error: " prefix dropped), or the protocol error when it said nothing."""
    lines = [line.strip() for line in server_output.splitlines() if line.strip()]
    if not lines:
        return f"the MCP server closed the connection unexpectedly ({error})"
    # The program name can contain spaces ("python.exe -m mcp_server"), hence the lazy match.
    return "the MCP server failed to start: " + re.sub(r"^.*?: error: ", "", lines[-1], count=1)


# --- Text output: a readable view of exactly what the server returned -------------------------------

def _yes_no(value: bool | None) -> str:
    return "n/a" if value is None else "yes" if value else "no"


def _rows(pairs: list[tuple[str, object]], indent: str = "") -> list[str]:
    width = max(len(label) for label, _ in pairs)
    return [f"{indent}{label:<{width}}  {value}" for label, value in pairs]


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=\.)\s", " ".join(text.split()), maxsplit=1)[0]


def format_discover(d: dict) -> str:
    caps, server, descriptions = d["capabilities"], d["server"], d.get("descriptions", {})
    lines = _rows([("MCP server", f"{server['name']} (version {server['version'] or 'n/a'})"),
                   ("Transport", d["transport"]),
                   ("Server role", f"{caps['role']['configured']} (supported: {', '.join(caps['role']['supported'])})")])
    lines.append(f"  {caps['role']['note']}")
    lines += ["", f"Tools ({len(d['tools'])})"]
    lines += _rows([(t, _first_sentence(descriptions.get(t, ""))) for t in d["tools"]], indent="  ")
    lines.append(f"Resources ({len(d['resources'])})")
    for uri, row in zip(d["resources"], _rows([(r, _first_sentence(descriptions.get(r, "")))
                                               for r in d["resources"]], indent="  ")):
        lines.append(row)
        if uri == SUBJECTS_URI:  # the resource's content, read through MCP
            lines.append(f"    {len(d['subjects'])} subjects: {', '.join(d['subjects'])}")
    lines += ["", f"Capabilities (contract v{caps['contract_version']})",
              f"  Configurations (default: {caps['default_configuration']})"]
    lines += _rows([(c["name"], c["summary"]) for c in caps["configurations"]], indent="    ")
    judgement = caps["judgement"]
    lines += _rows([("Judges", f"{', '.join(judgement['judges'])} (--judge; off by default)"),
                    ("Question", f"up to {caps['options']['question_max_chars']} characters"),
                    ("Date filter", caps["options"]["updated_on_or_after"]),
                    ("Access filter", caps["security"]["access_filter"]),
                    ("Security audit", caps["security"]["security_audit"])], indent="  ")
    return "\n".join(lines)


def format_health(h: dict) -> str:
    return "\n".join(_rows([("Ready", _yes_no(h["ready"])), ("Collection state", h["collection_state"]),
                            ("Index present", _yes_no(h["index_present"])),
                            ("Chunks", "n/a" if h["chunk_count"] is None else h["chunk_count"]),
                            ("Data plane reachable", _yes_no(h["data_plane_reachable"]))]))


def format_ask(r: dict) -> str:
    audit = r["security_audit"]
    pairs = [("Status", r["status"]), ("Configuration", r["config"]), ("Role", r["role"]),
             ("Candidates", r["retrieval"]["candidates_considered"])]
    if r["planned_subjects"]:
        pairs.append(("Planned subjects", ", ".join(r["planned_subjects"])))
    if r["cutoff"]:
        pairs.append(("Updated on or after", r["cutoff"]))
    lines = _rows(pairs)
    if audit["violation"]:
        # The projection has already withheld answer, sources and judgement; show only the audit.
        return "\n".join([*lines, "", f"SECURITY VIOLATION: {audit['explanation']}",
                          f"Violating sources: {audit['violating_source_count']} (names are never sent over MCP)"])
    if r["status"] == "not_found":
        lines += ["", "not_found: no content above the relevance threshold for this role (a normal result)."]
    lines += ["", "Answer", r["answer"], "", f"Sources ({len(r['sources'])})"]
    for s in r["sources"]:
        score = "n/a" if s["rerank_score"] is None else f"{s['rerank_score']:.2f}"
        lines.append(f"  {s['rank']}. {s['source']} ({s['corpus']}, updated {s['last_updated']}, rerank {score})"
                     f" subjects: {', '.join(s['subjects'])}")
    lines.append("Security audit: passed")
    if (j := r["judgement"]) is not None:
        completeness = "n/a" if j["completeness"] is None else f"{j['completeness']:.2f}"
        lines.append(f"Judgement: faithfulness {j['faithfulness']:.2f}, context relevance "
                     f"{j['context_relevance']:.2f}, completeness {completeness}, refused {_yes_no(j['refused'])}")
    return "\n".join(lines)


_FORMATTERS = {"discover": format_discover, "health": format_health, "ask": format_ask}


if __name__ == "__main__":
    main()
