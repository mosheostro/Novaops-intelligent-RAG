"""mcp_client.py — the minimal Stage 1 client. Its functions run against the real
server over the SDK's in-memory transport (infrastructure patched, no AWS); one
test starts the real server process over STDIO for discovery only, which needs
no network. Skipped without the optional `mcp` dependency."""
import ast
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager, redirect_stdout
from pathlib import Path
from unittest.mock import patch

if importlib.util.find_spec("mcp") is None:
    raise unittest.SkipTest("MCP tests need the optional dependency: pip install -r requirements-mcp.txt")

REQUIRED_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
                "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION")
for _name in REQUIRED_ENV:
    os.environ.setdefault(_name, "test-value")

import anyio  # noqa: E402
from mcp import Client  # noqa: E402
from opensearchpy.exceptions import OpenSearchException  # noqa: E402

import mcp_client  # noqa: E402
import mcp_server  # noqa: E402
from subjects import SUBJECTS  # noqa: E402
from tests.test_mcp_server import GENERATED_ANSWER, _ask_result, _health  # noqa: E402

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


class RunStage1Tests(_Patched):
    def test_adds_health_and_one_answer_exactly_as_the_server_returns_them(self):
        result = _with_session("employee", lambda s: mcp_client.run_stage1(s, "What benefits are available?"))
        self.assertEqual(set(result), {"tools", "resources", "capabilities", "subjects", "health", "ask_rag"})
        self.assertEqual(result["health"], mcp_server.project_health(_health()).model_dump(mode="json"))
        self.assertEqual(result["ask_rag"], mcp_server.project_ask_result(_ask_result()).model_dump(mode="json"))
        self.assertEqual(result["ask_rag"]["answer"], GENERATED_ANSWER)
        self.assertEqual(self.ask.call_args.args[1:3], ("What benefits are available?", "employee"))

    def test_uses_the_default_question(self):
        _with_session("manager", mcp_client.run_stage1)
        self.assertEqual(self.ask.call_args.args[1:3], (mcp_client.DEFAULT_QUESTION, "manager"))

    def test_a_tool_error_surfaces_the_servers_own_message(self):
        self.ask.side_effect = OpenSearchException("SECRET endpoint https://x.aoss.amazonaws.com")

        async def run(session):
            try:
                await mcp_client.run_stage1(session)
            except mcp_client.ToolCallError as exc:  # caught inside the session, as main() does
                return exc

        error = _with_session("employee", run)
        self.assertIsInstance(error, mcp_client.ToolCallError)
        message = str(error)
        self.assertIn("service_unavailable", message)
        self.assertNotIn("SECRET", message)


class MainTests(_Patched):
    def _main(self, argv):
        @asynccontextmanager
        async def in_process(role, **_kwargs):
            async with Client(mcp_server.build_server(role)) as c:
                yield c.session

        out = io.StringIO()
        with patch("mcp_client.connect", in_process), redirect_stdout(out):
            mcp_client.main(argv)
        return out.getvalue()

    def test_prints_the_stage1_result_as_json(self):
        printed = json.loads(self._main(["--role", "employee", "--question", "Holidays?"]))
        self.assertEqual(printed["tools"], STAGE1_TOOLS)
        self.assertEqual(printed["ask_rag"]["role"], "employee")
        self.assertEqual(self.ask.call_args.args[1], "Holidays?")

    def test_a_tool_error_exits_with_the_servers_message(self):
        self.ask.side_effect = OpenSearchException("SECRET")
        err = io.StringIO()
        with patch("sys.stderr", err), self.assertRaises(SystemExit) as exit_:
            self._main(["--role", "employee"])
        self.assertEqual(exit_.exception.code, 1)
        self.assertIn("service_unavailable", err.getvalue())
        self.assertNotIn("SECRET", err.getvalue())


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
            mcp_client.main(["--role", "user", "--question", "q"])
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

        async def discovery_only(session, question):
            return await mcp_client.discover(session)

        err = io.StringIO()
        with patch("mcp_client.connect", connect_with_placeholder_config), patch("mcp_client.run_stage1",
                                                                                 discovery_only), \
                patch("sys.stderr", err), redirect_stdout(io.StringIO()) as out:
            mcp_client.main(["--role", "employee"])
        self.assertEqual(json.loads(out.getvalue())["tools"], STAGE1_TOOLS)
        self.assertNotIn("Traceback", err.getvalue())


class ThinClientTests(unittest.TestCase):
    def test_imports_only_the_standard_library_and_the_mcp_sdk(self):
        tree = ast.parse((ROOT / "mcp_client.py").read_text(encoding="utf-8"))
        roots = {alias.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
        roots |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        project = {p.stem for p in ROOT.glob("*.py")} | {"ui", "tests"}
        self.assertEqual(roots & project, set())  # no RAG core, no mcp_server, no UI
        self.assertEqual(roots - set(sys.stdlib_module_names), {"anyio", "mcp"})


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
