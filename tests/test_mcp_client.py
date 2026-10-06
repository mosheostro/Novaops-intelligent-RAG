"""mcp_client.py — the MCP client: CLI commands, the synchronous HTTP functions and
their error handling. Its functions run against the real server over the SDK's
in-memory transport (infrastructure patched, no AWS); the real-process tests start
the server over STDIO for discovery only, which needs no network (real HTTP is in
test_mcp_http.py). Skipped without the optional `mcp` dependency."""
import ast
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

if importlib.util.find_spec("mcp") is None:
    raise unittest.SkipTest("MCP tests need the optional dependency: pip install -r requirements-mcp.txt")

REQUIRED_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
                "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION")
for _name in REQUIRED_ENV:
    os.environ.setdefault(_name, "test-value")

import anyio  # noqa: E402
import httpx2  # noqa: E402
from mcp import Client, MCPError  # noqa: E402
from opensearchpy.exceptions import OpenSearchException  # noqa: E402

import mcp_client  # noqa: E402
import mcp_server  # noqa: E402
from subjects import SUBJECTS  # noqa: E402
from tests.test_mcp_server import (  # noqa: E402
    GENERATED_ANSWER, JUDGEMENT, SECRET_ENDPOINT, _ask_result, _health,
)

ROOT = Path(__file__).resolve().parent.parent
STAGE1_TOOLS = ["ask_rag", "get_rag_capabilities", "health_check"]


def _with_session(role, action):
    """Run `action(session)` with the client's ClientSession connected in-process to the real server."""
    async def run():
        async with Client(mcp_server.build_server(role)) as c:
            return await action(c.session)
    return anyio.run(run)


class _Patched(unittest.TestCase):
    def setUp(self):
        self.ask = patch("ask.ask", return_value=_ask_result()).start()
        self.collection_health = patch("manage.collection_health", return_value=_health()).start()
        self.aoss_client = patch("manage.aoss_client").start()
        self.opensearch_client = patch("client.opensearch_client").start()
        self.addCleanup(patch.stopall)


class ServerParametersTests(unittest.TestCase):
    def test_launches_the_server_module_with_the_role_from_the_project_root(self):
        params = mcp_client.server_parameters("employee")
        self.assertEqual(params.command, sys.executable)
        self.assertEqual(params.args, ["-m", "mcp_server", "--role", "employee"])
        self.assertEqual(Path(params.cwd), ROOT)
        self.assertIsNone(params.env)

    def test_role_is_passed_through_unvalidated(self):
        # The server is the single source of truth for roles; the client never decides.
        self.assertEqual(mcp_client.server_parameters("boss").args[-1], "boss")

    def test_extra_environment_is_passed_to_the_server(self):
        self.assertEqual(mcp_client.server_parameters("manager", env={"X": "1"}).env, {"X": "1"})


class DiscoverTests(_Patched):
    def test_returns_the_static_surface_without_infrastructure_calls(self):
        result = _with_session("employee", mcp_client.discover)
        self.assertEqual(result["tools"], STAGE1_TOOLS)
        self.assertEqual(result["resources"], ["rag://subjects"])
        self.assertEqual(result["capabilities"], mcp_server.build_capabilities("employee").model_dump(mode="json"))
        self.assertEqual(result["subjects"], list(SUBJECTS))
        for mock in (self.ask, self.collection_health, self.aoss_client, self.opensearch_client):
            mock.assert_not_called()


def _in_process_http(role="employee"):
    """Stands in for connect_http: the real server, in-process, recording the URL it was given."""
    urls = []

    @asynccontextmanager
    async def connect_http(url, read_timeout=None):
        urls.append((url, read_timeout))
        async with Client(mcp_server.build_server(role)) as c:
            yield c.session
    return connect_http, urls


def _failing_http(*errors):
    """Stands in for connect_http: fails the way the SDK does, inside nested task groups."""
    @asynccontextmanager
    async def connect_http(url, read_timeout=None):
        raise ExceptionGroup("unhandled errors in a TaskGroup", [ExceptionGroup("inner", list(errors))])
        yield  # pragma: no cover
    return connect_http


URL = "http://127.0.0.1:8000/mcp"


class FacadeTests(_Patched):
    """The synchronous facade the dashboard uses: plain values in, plain dicts out."""

    def setUp(self):
        super().setUp()
        connect_http, self.urls = _in_process_http()
        patch("mcp_client.connect_http", connect_http).start()

    def test_describe_returns_the_surface_with_server_identity_and_transport(self):
        result = mcp_client.describe(URL)
        self.assertEqual(self.urls, [(URL, None)])  # the SDK's own timeouts unless one is given
        self.assertEqual(result["tools"], STAGE1_TOOLS)
        self.assertEqual(result["resources"], ["rag://subjects"])
        self.assertEqual(result["subjects"], list(SUBJECTS))
        self.assertEqual(result["capabilities"]["role"]["configured"], "employee")
        self.assertEqual(result["server"]["name"], "novaops-knowledge-base")
        self.assertEqual(result["transport"], "streamable-http")
        for mock in (self.ask, self.collection_health, self.aoss_client, self.opensearch_client):
            mock.assert_not_called()

    def test_every_call_passes_an_explicit_read_timeout_to_the_connection(self):
        mcp_client.describe(URL, read_timeout=120)
        mcp_client.check_health(URL, read_timeout=120)
        mcp_client.ask(URL, "Holidays?", read_timeout=120)
        self.assertEqual(self.urls, [(URL, 120)] * 3)

    def test_check_health_returns_the_servers_projection(self):
        self.assertEqual(mcp_client.check_health(URL), mcp_server.project_health(_health()).model_dump(mode="json"))

    def test_ask_sends_only_the_given_arguments_and_returns_the_projection(self):
        result = mcp_client.ask(URL, "Holidays?")
        self.assertEqual(result, mcp_server.project_ask_result(_ask_result()).model_dump(mode="json"))
        args, kwargs = self.ask.call_args
        self.assertEqual(args[1:4], ("Holidays?", "employee", mcp_server.DEFAULT_CONFIG))  # the server's default
        self.assertEqual(kwargs, {"judge": False, "cutoff": None})

    def test_ask_passes_config_judge_and_cutoff_through(self):
        mcp_client.ask(URL, "Holidays?", config="baseline", judge=True, updated_on_or_after=date(2025, 1, 31))
        args, kwargs = self.ask.call_args
        self.assertEqual(args[3], "baseline")
        self.assertEqual(kwargs, {"judge": True, "cutoff": date(2025, 1, 31)})

    def test_a_tool_error_is_a_plain_tool_call_error_with_the_servers_message(self):
        self.ask.side_effect = OpenSearchException("SECRET endpoint")
        with self.assertRaises(mcp_client.ToolCallError) as caught:  # not wrapped in an ExceptionGroup
            mcp_client.ask(URL, "Holidays?")
        self.assertIn("service_unavailable", str(caught.exception))
        self.assertNotIn("SECRET", str(caught.exception))

    def test_an_invalid_argument_is_a_tool_call_error(self):
        with self.assertRaises(mcp_client.ToolCallError):
            mcp_client.ask(URL, "   ")
        self.ask.assert_not_called()


class ConnectHttpTimeoutTests(unittest.TestCase):
    """connect_http keeps the SDK's HTTP client (and its 300 s read timeout) by default; an
    explicit read_timeout gets its own client — no global configuration is changed."""

    def _http_client_used(self, **kwargs):
        seen = []

        @asynccontextmanager
        async def fake_transport(url, http_client=None):
            seen.append(http_client)
            raise RuntimeError("stop")
            yield  # pragma: no cover

        async def run():
            async with mcp_client.connect_http(URL, **kwargs):
                pass  # pragma: no cover

        with patch("mcp_client.streamable_http_client", fake_transport), self.assertRaises(RuntimeError):
            anyio.run(run)
        return seen[0]

    def test_default_uses_the_sdks_own_client(self):
        self.assertIsNone(self._http_client_used())

    def test_an_explicit_read_timeout_shortens_only_the_read_timeout(self):
        timeout = self._http_client_used(read_timeout=120).timeout
        self.assertEqual(timeout.read, 120)
        self.assertEqual(timeout.connect, 30)


class ServerUrlTests(unittest.TestCase):
    """The URL is checked before any connection attempt, with a message that says how to fix it."""

    INVALID = {
        "127.0.0.1:8000": "it must start with http://, e.g. http://127.0.0.1:8000/mcp",
        "localhost:8000/mcp": "it must start with http://, e.g. http://localhost:8000/mcp",
        "ftp://127.0.0.1:8000/mcp": "only http:// and https:// are supported",
        "http:///mcp": "the host is missing, e.g. http://127.0.0.1:8000/mcp",
        "http://127.0.0.1:8000": "the endpoint path is missing; the NovaOps MCP endpoint is /mcp, "
                                 "e.g. http://127.0.0.1:8000/mcp",
        "http://127.0.0.1:8000/": "the endpoint path is missing",
        "http://127.0.0.1:port/mcp": "the port must be a number",
        "": "it must start with http://",
    }

    def test_an_invalid_url_is_refused_before_connecting_with_a_fix(self):
        connect_http = MagicMock()
        for url, expected in self.INVALID.items():
            for call in (lambda: mcp_client.describe(url), lambda: mcp_client.check_health(url),
                         lambda: mcp_client.ask(url, "q")):
                with self.subTest(url=url), patch("mcp_client.connect_http", connect_http), \
                        self.assertRaises(mcp_client.InvalidServerUrlError) as caught:
                    call()
                self.assertTrue(str(caught.exception).startswith(f"invalid MCP server URL {url!r}: "))
                self.assertIn(expected, str(caught.exception))
        connect_http.assert_not_called()

    def test_valid_urls_pass(self):
        for url in (URL, "http://localhost:8001/mcp", "http://[::1]:8000/mcp", "https://example.com/mcp"):
            with self.subTest(url=url):
                self.assertIsNone(mcp_client.check_url(url))


class ServerUnavailableTests(unittest.TestCase):
    """Connection, protocol and timeout failures become one exception type with a kind and a
    message built from fixed wording plus the URL the caller gave — never the underlying
    exception's text, no chained cause, no ExceptionGroup."""

    FAILURES = [
        ("refused", httpx2.ConnectError("All connection attempts failed SECRET"), "unreachable",
         "could not connect to 127.0.0.1:8000 (connection refused or unknown host). Is the MCP server running? "
         "Start it with: python mcp_server.py --transport streamable-http --role employee --port 8000"),
        ("connect timeout", httpx2.ConnectTimeout("SECRET"), "timeout",
         "the MCP server at http://127.0.0.1:8000/mcp did not respond in time"),
        ("read timeout", httpx2.ReadTimeout("SECRET"), "timeout",
         "the MCP server at http://127.0.0.1:8000/mcp did not respond in time"),
        ("wrong path", MCPError(code=-32601, message="Not Found"), "not_found",
         "127.0.0.1:8000 answered, but there is no MCP endpoint at '/mcp' (HTTP 404); "
         "the NovaOps MCP endpoint is /mcp, e.g. http://127.0.0.1:8000/mcp"),
        ("not an MCP server", MCPError(code=-32600, message="Unexpected content type: text/html SECRET"),
         "not_mcp", "http://127.0.0.1:8000/mcp answered, but not as an MCP server"),
        ("dropped", httpx2.RemoteProtocolError("SECRET"), "dropped",
         "the connection to http://127.0.0.1:8000/mcp was closed unexpectedly"),
        ("closed", MCPError(code=-32000, message="Connection closed SECRET"), "dropped",
         "the connection to http://127.0.0.1:8000/mcp was closed unexpectedly"),
    ]

    def test_each_failure_has_its_own_kind_and_safe_message(self):
        calls = {"describe": lambda: mcp_client.describe(URL), "check_health": lambda: mcp_client.check_health(URL),
                 "ask": lambda: mcp_client.ask(URL, "q")}
        for name, error, kind, message in self.FAILURES:
            for call_name, call in calls.items():
                with self.subTest(failure=name, call=call_name), \
                        patch("mcp_client.connect_http", _failing_http(error)):
                    with self.assertRaises(mcp_client.ServerUnavailableError) as caught:
                        call()
                    self.assertEqual(caught.exception.kind, kind)
                    self.assertEqual(str(caught.exception), message)
                    self.assertNotIn("SECRET", str(caught.exception))
                    self.assertIsNone(caught.exception.__cause__)
                    self.assertIsNone(caught.exception.__context__)

    def test_https_to_the_plain_http_server_says_so(self):
        with patch("mcp_client.connect_http", _failing_http(httpx2.ConnectError("[SSL: WRONG_VERSION_NUMBER]"))), \
                self.assertRaises(mcp_client.ServerUnavailableError) as caught:
            mcp_client.describe("https://127.0.0.1:8000/mcp")
        self.assertIn("The NovaOps MCP server speaks plain http; try http://127.0.0.1:8000/mcp",
                      str(caught.exception))
        self.assertNotIn("SSL", str(caught.exception))

    def test_credentials_and_query_in_the_url_are_never_echoed(self):
        with patch("mcp_client.connect_http", _failing_http(httpx2.ReadTimeout(""))), \
                self.assertRaises(mcp_client.ServerUnavailableError) as caught:
            mcp_client.describe("http://user:hunter2@127.0.0.1:8000/mcp?token=abc")
        self.assertEqual(str(caught.exception), "the MCP server at http://127.0.0.1:8000/mcp did not respond in time")

    def test_a_programming_error_is_not_disguised_as_an_unavailable_server(self):
        with patch("mcp_client.connect_http", _failing_http(ValueError("bug"))), \
                self.assertRaises(BaseExceptionGroup) as caught:
            mcp_client.describe(URL)
        self.assertIsNone(caught.exception.subgroup(mcp_client.ServerUnavailableError))


class CliTests(_Patched):
    """`mcp_client.py COMMAND (--url URL | --role ROLE) [--json]`. Both transports are
    driven in-process against the real server — infrastructure patched, no AWS."""

    def _main(self, argv, connect_http=None):
        connect_http = connect_http or _in_process_http()[0]
        stdio_roles = []

        @asynccontextmanager
        async def connect(role, env=None, errlog=None):
            stdio_roles.append(role)
            async with Client(mcp_server.build_server(role)) as c:
                yield c.session

        out, err = io.StringIO(), io.StringIO()
        with patch("mcp_client.connect_http", connect_http), patch("mcp_client.connect", connect), \
                redirect_stdout(out), patch("sys.stderr", err):
            try:
                mcp_client.main(argv)
                code = 0
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue(), stdio_roles

    def assertNoAwsCall(self):
        for mock in (self.ask, self.collection_health, self.aoss_client, self.opensearch_client):
            mock.assert_not_called()

    # --- discover -----------------------------------------------------------------------------

    def test_discover_shows_the_mcp_surface_as_text(self):
        code, out, err, stdio_roles = self._main(["discover", "--url", URL])
        self.assertEqual(code, 0)
        for expected in ("MCP server", "novaops-knowledge-base (version 0.2.0)", "Transport", "streamable-http",
                         "Server role", "employee (supported: employee, manager)",
                         "Tools (3)", "Resources (1)", "Capabilities (contract v1)",
                         "Configurations (default: filter + rerank dynamic)", "baseline",
                         f"{len(SUBJECTS)} subjects: {', '.join(SUBJECTS)}"):
            self.assertIn(expected, out)
        self.assertEqual(stdio_roles, [])
        self.assertNoAwsCall()

    def test_discover_text_shows_each_tool_and_resource_with_the_servers_own_description(self):
        async def published(session):
            tools, resources = await session.list_tools(), await session.list_resources()
            return ({t.name: t.description for t in tools.tools},
                    {str(r.uri): r.description for r in resources.resources})

        tools, resources = _with_session("employee", published)
        _, out, _, _ = self._main(["discover", "--url", URL])
        lines = out.splitlines()
        for name, description in {**tools, **resources}.items():
            first_sentence = " ".join(description.split()).split(". ")[0].rstrip(".") + "."
            with self.subTest(name=name):
                self.assertTrue(any(re.fullmatch(rf"  {re.escape(name)}\s+{re.escape(first_sentence)}", line)
                                    for line in lines), (name, first_sentence))
        # The subjects are shown as what they are: the content of the rag://subjects resource.
        resource_line = next(i for i, line in enumerate(lines) if line.startswith("  rag://subjects"))
        self.assertIn(f"{len(SUBJECTS)} subjects:", lines[resource_line + 1])

    def test_discover_descriptions_follow_the_server_not_the_client(self):
        server = mcp_server.build_server("employee")
        server._tool_manager.get_tool("health_check").description = "Changed on the server. Second sentence."

        @asynccontextmanager
        async def connect_http(url, read_timeout=None):
            async with Client(server) as c:
                yield c.session

        _, out, _, _ = self._main(["discover", "--url", URL], connect_http)
        self.assertRegex(out, r"  health_check\s+Changed on the server\.\n")

    def test_discover_json_is_the_facades_result(self):
        _, out, _, _ = self._main(["discover", "--url", URL, "--json"])
        printed = json.loads(out)
        with patch("mcp_client.connect_http", _in_process_http()[0]):
            self.assertEqual(printed, mcp_client.describe(URL))  # exactly the facade's result: no text-only extras
        self.assertEqual(set(printed), {"server", "transport", "tools", "resources", "capabilities", "subjects"})
        self.assertEqual(printed["transport"], "streamable-http")
        self.assertEqual(printed["tools"], STAGE1_TOOLS)
        self.assertEqual(printed["capabilities"], mcp_server.build_capabilities("employee").model_dump(mode="json"))

    def test_discover_over_stdio_starts_a_server_with_the_role(self):
        code, out, _, stdio_roles = self._main(["discover", "--role", "manager", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(stdio_roles, ["manager"])
        printed = json.loads(out)
        self.assertEqual(printed["transport"], "stdio")
        self.assertEqual(printed["capabilities"]["role"]["configured"], "manager")
        self.assertNoAwsCall()

    # --- health -------------------------------------------------------------------------------

    def test_health_shows_the_safe_projection(self):
        code, out, _, _ = self._main(["health", "--url", URL])
        self.assertEqual(code, 0)
        self.assertRegex(out, r"Ready\s+yes")
        self.assertRegex(out, r"Collection state\s+ACTIVE")
        self.assertRegex(out, r"Chunks\s+400")
        self.assertNotIn(SECRET_ENDPOINT, out)
        self.ask.assert_not_called()

    def test_health_json_is_the_projection(self):
        _, out, _, _ = self._main(["health", "--url", URL, "--json"])
        self.assertEqual(json.loads(out), mcp_server.project_health(_health()).model_dump(mode="json"))

    # --- ask ----------------------------------------------------------------------------------

    def test_ask_passes_the_options_and_shows_answer_and_sources(self):
        code, out, _, _ = self._main(["ask", "How does PTO accrue?", "--url", URL, "--config", "baseline",
                                      "--judge", "--updated-on-or-after", "2025-01-31"])
        self.assertEqual(code, 0)
        args, kwargs = self.ask.call_args
        self.assertEqual(args[1:4], ("How does PTO accrue?", "employee", "baseline"))
        self.assertEqual(kwargs, {"judge": True, "cutoff": date(2025, 1, 31)})
        for expected in ("Status", "selected", GENERATED_ANSWER, "Sources (2)", "1. pto.md", "2. holidays.md",
                         "Security audit: passed"):
            self.assertIn(expected, out)
        for leak in ("SENTINEL-CHUNK-TEXT", "vector_score", "0.87"):  # no chunk text, no vector scores
            self.assertNotIn(leak, out)

    def test_ask_defaults_leave_the_choice_to_the_server(self):
        self._main(["ask", "Holidays?", "--url", URL])
        args, kwargs = self.ask.call_args
        self.assertEqual(args[3], mcp_server.DEFAULT_CONFIG)
        self.assertEqual(kwargs, {"judge": False, "cutoff": None})

    def test_ask_json_is_the_projection(self):
        _, out, _, _ = self._main(["ask", "Holidays?", "--url", URL, "--json"])
        self.assertEqual(json.loads(out), mcp_server.project_ask_result(_ask_result()).model_dump(mode="json"))

    def test_ask_shows_the_judgement_when_requested(self):
        self.ask.return_value = _ask_result(judgement=JUDGEMENT)
        _, out, _, _ = self._main(["ask", "Holidays?", "--url", URL, "--judge"])
        self.assertIn("Judgement: faithfulness 0.90, context relevance 1.00, completeness 0.80, refused no", out)

    def test_ask_with_a_security_violation_shows_only_the_audit(self):
        self.ask.return_value = _ask_result(violation=True, judgement=JUDGEMENT)
        code, out, _, _ = self._main(["ask", "Holidays?", "--url", URL])
        self.assertEqual(code, 0)
        self.assertIn(f"SECURITY VIOLATION: {mcp_server.SECURITY_VIOLATION_EXPLANATION}", out)
        self.assertIn("Violating sources: 1", out)
        for withheld in ("SENTINEL", "Sources (", "Judgement:", "Security audit: passed"):
            self.assertNotIn(withheld, out)

    def test_ask_not_found_is_a_normal_result(self):
        self.ask.return_value = _ask_result(status="not_found")
        code, out, _, _ = self._main(["ask", "Holidays?", "--url", URL])
        self.assertEqual(code, 0)
        self.assertIn("not_found: no content above the relevance threshold", out)
        self.assertIn("Sources (0)", out)

    def test_ask_over_stdio(self):
        code, out, _, stdio_roles = self._main(["ask", "Holidays?", "--role", "manager", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(stdio_roles, ["manager"])
        self.assertEqual(self.ask.call_args.args[2], "manager")  # the server's role reached ask()
        self.assertIn("answer", json.loads(out))

    # --- invocation and errors ----------------------------------------------------------------

    def test_invalid_invocations_are_usage_errors(self):
        for argv in ([], ["--url", URL], ["discover"], ["discover", "--url", URL, "--role", "employee"],
                     ["ask", "--url", URL], ["bogus", "--url", URL], ["health", "--url", URL, "extra"],
                     ["ask", "q", "--url", URL, "--updated-on-or-after", "2025/01/31"]):
            with self.subTest(argv=argv):
                code, out, err, stdio_roles = self._main(argv)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("usage:", err)
                self.assertEqual(stdio_roles, [])
        self.assertNoAwsCall()

    def test_a_bad_date_says_which_format_is_expected(self):
        _, _, err, _ = self._main(["ask", "q", "--url", URL, "--updated-on-or-after", "2025/01/31"])
        self.assertIn("expected an ISO date YYYY-MM-DD (e.g. 2025-01-31), got '2025/01/31'", err)

    def test_help_lists_the_commands_and_examples(self):
        code, out, _, _ = self._main(["--help"])
        self.assertEqual(code, 0)
        for expected in ("discover", "health", "ask", "python mcp_client.py discover --url"):
            self.assertIn(expected, out)

    def test_an_invalid_url_is_a_usage_error_that_shows_the_fix(self):
        connect_http = MagicMock()
        code, out, err, _ = self._main(["discover", "--url", "127.0.0.1:8000"], connect_http)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("error: invalid MCP server URL '127.0.0.1:8000': it must start with http://, "
                      "e.g. http://127.0.0.1:8000/mcp", err)
        connect_http.assert_not_called()

    def test_an_unavailable_server_is_one_line_on_stderr(self):
        for command in (["discover"], ["health"], ["ask", "q"]):
            with self.subTest(command=command):
                code, out, err, _ = self._main([*command, "--url", URL],
                                               _failing_http(httpx2.ConnectError("SECRET")))
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertEqual(len(err.strip().splitlines()), 1)
                self.assertTrue(err.startswith("error: could not connect to 127.0.0.1:8000"))
                self.assertNotIn("SECRET", err)

    def test_a_tool_error_exits_with_the_servers_safe_message(self):
        self.ask.side_effect = OpenSearchException("SECRET")
        for target in (["--url", URL], ["--role", "employee"]):
            with self.subTest(target=target):
                code, out, err, _ = self._main(["ask", "q", *target])
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertIn("tool error: ", err)
                self.assertIn("service_unavailable", err)
                self.assertNotIn("SECRET", err)

    def test_an_invalid_question_is_a_tool_error_from_the_server(self):
        code, _, err, _ = self._main(["ask", "   ", "--url", URL])
        self.assertEqual(code, 1)
        self.assertIn("tool error: ", err)
        self.ask.assert_not_called()

    def test_a_programming_error_is_not_disguised(self):
        with self.assertRaises(BaseExceptionGroup) as caught:
            self._main(["discover", "--url", URL], _failing_http(ValueError("bug")))
        self.assertIsNone(caught.exception.subgroup(mcp_client.ServerUnavailableError))


class ServerRefusesToStartTests(unittest.TestCase):
    """A real server process with an unsupported role: it fails closed before the
    handshake, and the client must report that cleanly — no traceback, no
    ExceptionGroup — leaving the server's own refusal message as the explanation."""

    def test_unsupported_role_reports_the_servers_reason_cleanly(self):
        placeholders = {name: "test-value" for name in REQUIRED_ENV}
        connect = mcp_client.connect

        def connect_with_placeholder_config(role, env=None, errlog=None):
            return connect(role, env={**(env or {}), **placeholders}, errlog=errlog)

        err = io.StringIO()
        with patch("mcp_client.connect", connect_with_placeholder_config), patch("sys.stderr", err), \
                redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as exit_:
            mcp_client.main(["discover", "--role", "user"])
        self.assertEqual(exit_.exception.code, 1)
        self.assertEqual(out.getvalue(), "")
        message = err.getvalue()
        # The server's own reason, captured by the client — not "see above" (on a Windows
        # console the server process has no console of its own to print to).
        self.assertIn("MCP server failed", message)
        self.assertIn("unsupported role 'user'; expected one of ['employee', 'manager']", message)
        self.assertEqual(len(message.strip().splitlines()), 1)  # one line, not the argparse usage dump
        self.assertEqual(message.strip(), "error: the MCP server failed to start: unsupported role 'user'; "
                                          "expected one of ['employee', 'manager']")
        for noise in ("Traceback", "ExceptionGroup", "TaskGroup", "usage:", "mcp_server: error:"):
            self.assertNotIn(noise, message)

    def test_server_log_is_forwarded_after_a_successful_run(self):
        placeholders = {name: "test-value" for name in REQUIRED_ENV}
        connect = mcp_client.connect

        def connect_with_placeholder_config(role, env=None, errlog=None):
            return connect(role, env={**(env or {}), **placeholders}, errlog=errlog)

        err = io.StringIO()
        with patch("mcp_client.connect", connect_with_placeholder_config), \
                patch("sys.stderr", err), redirect_stdout(io.StringIO()) as out:
            mcp_client.main(["discover", "--role", "employee", "--json"])
        self.assertEqual(json.loads(out.getvalue())["tools"], STAGE1_TOOLS)
        self.assertNotIn("Traceback", err.getvalue())


class ThinClientTests(unittest.TestCase):
    def test_imports_only_the_standard_library_and_the_mcp_sdk(self):
        tree = ast.parse((ROOT / "mcp_client.py").read_text(encoding="utf-8"))
        roots = {alias.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
        roots |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        project = {p.stem for p in ROOT.glob("*.py")} | {"ui", "tests"}
        self.assertEqual(roots & project, set())  # no RAG core, no mcp_server, no UI
        # httpx2 is the MCP SDK's own HTTP client, imported only to recognise transport failures.
        self.assertEqual(roots - set(sys.stdlib_module_names), {"anyio", "httpx2", "mcp"})


class StdioDiscoveryIntegrationTests(unittest.TestCase):
    """The real server process over STDIO. Discovery makes no AWS call, so placeholder
    configuration is enough and no network is needed."""

    def test_discovers_the_stage1_surface_from_a_real_server_process(self):
        env = {name: "test-value" for name in REQUIRED_ENV}

        with tempfile.TemporaryFile("w+") as server_log:  # the server's stderr needs a real file
            async def run():
                async with mcp_client.connect("employee", env=env, errlog=server_log) as session:
                    return await mcp_client.discover(session)

            result = anyio.run(run)
        self.assertEqual(result["tools"], STAGE1_TOOLS)
        self.assertEqual(result["resources"], ["rag://subjects"])
        self.assertEqual(result["subjects"], list(SUBJECTS))
        self.assertEqual(result["capabilities"]["role"]["configured"], "employee")


if __name__ == "__main__":
    unittest.main()
