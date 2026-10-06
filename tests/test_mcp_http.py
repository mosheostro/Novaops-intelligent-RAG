"""Streamable HTTP end to end: real server processes on free loopback ports, reached
through mcp_client's facade and through raw HTTP. Discovery and argument
validation make no AWS call, so placeholder configuration is enough and no network
beyond loopback is used. Skipped without the optional `mcp` dependency."""
import importlib.util
import io
import json
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

if importlib.util.find_spec("mcp") is None:
    raise unittest.SkipTest("MCP tests need the optional dependency: pip install -r requirements-mcp.txt")

import anyio  # noqa: E402

import mcp_client  # noqa: E402
from subjects import SUBJECTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
                "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION")
PLACEHOLDER = "test-value"  # a valid-format region too: boto3 validates the region at import
STAGE1_TOOLS = ["ask_rag", "get_rag_capabilities", "health_check"]
READY_TIMEOUT = 30
INITIALIZE = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                         "clientInfo": {"name": "test", "version": "0"}}}
JSON_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _HttpServer:
    """One real `mcp_server.py --transport streamable-http` process; its stdout and
    stderr go to a temporary file so the tests can inspect what it logged."""

    def __init__(self, role: str):
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}/mcp"
        self.log = tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", **{name: PLACEHOLDER for name in REQUIRED_ENV}}
        self.process = subprocess.Popen(
            [sys.executable, "mcp_server.py", "--transport", "streamable-http", "--role", role,
             "--port", str(self.port)],
            cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + READY_TIMEOUT
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"MCP server exited during startup:\n{self.output()}")
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.2).close()
                return
            except OSError:
                if time.monotonic() > deadline:
                    self.stop()
                    raise RuntimeError("MCP server did not start listening in time")
                time.sleep(0.1)

    def output(self) -> str:
        self.log.seek(0)
        return self.log.read()

    def stop(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=10)
        self.log.close()


def _post(url: str, body: dict, **headers) -> tuple[int, dict, str]:
    request = urllib.request.Request(url, json.dumps(body).encode(), {**JSON_HEADERS, **headers})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read().decode()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, dict(error.headers), error.read().decode()


class StreamableHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # In-process MCPServer instances elsewhere in the suite configure root logging at INFO;
        # keep the SDK HTTP client's per-request INFO lines out of the test output.
        http_log = logging.getLogger("httpx2")
        cls.addClassCleanup(http_log.setLevel, http_log.level)
        http_log.setLevel(logging.WARNING)
        cls.employee = _HttpServer("employee")
        cls.addClassCleanup(cls.employee.stop)
        cls.manager = _HttpServer("manager")
        cls.addClassCleanup(cls.manager.stop)

    def test_describe_discovers_the_stage1_surface_over_http(self):
        result = mcp_client.describe(self.employee.url)
        self.assertEqual(result["tools"], STAGE1_TOOLS)
        self.assertEqual(result["resources"], ["rag://subjects"])
        self.assertEqual(result["subjects"], list(SUBJECTS))
        self.assertEqual(result["server"], {"name": "novaops-knowledge-base", "version": "0.2.0"})
        self.assertEqual(result["transport"], "streamable-http")
        self.assertEqual(result["capabilities"]["role"]["configured"], "employee")

    def test_each_server_process_reports_its_own_startup_role(self):
        self.assertEqual(mcp_client.describe(self.manager.url)["capabilities"]["role"]["configured"], "manager")

    def test_http_and_stdio_expose_the_same_surface(self):
        with tempfile.TemporaryFile("w+") as server_log:
            async def over_stdio():
                env = {name: PLACEHOLDER for name in REQUIRED_ENV}
                async with mcp_client.connect("employee", env=env, errlog=server_log) as session:
                    return await mcp_client.discover(session)

            stdio = anyio.run(over_stdio)
        http = mcp_client.describe(self.employee.url)
        self.assertEqual({key: http[key] for key in stdio}, stdio)

    def test_a_wrong_path_on_a_running_server_says_where_the_endpoint_is(self):
        with self.assertRaises(mcp_client.ServerUnavailableError) as caught:
            mcp_client.describe(f"http://127.0.0.1:{self.employee.port}/wrong")
        self.assertEqual(caught.exception.kind, "not_found")
        self.assertIn("the NovaOps MCP endpoint is /mcp", str(caught.exception))

    def test_https_to_the_running_server_suggests_http(self):
        with self.assertRaises(mcp_client.ServerUnavailableError) as caught:
            mcp_client.describe(f"https://127.0.0.1:{self.employee.port}/mcp")
        self.assertIn(f"try http://127.0.0.1:{self.employee.port}/mcp", str(caught.exception))

    def test_the_cli_discovers_a_real_server(self):
        out = io.StringIO()
        with redirect_stdout(out):
            mcp_client.main(["discover", "--url", self.manager.url])
        self.assertIn("novaops-knowledge-base", out.getvalue())
        self.assertRegex(out.getvalue(), r"Server role\s+manager")
        self.assertIn("Tools (3)", out.getvalue())
        self.assertIn("novaops-knowledge-base (version 0.2.0)", out.getvalue())

    def test_a_tool_error_over_http_is_a_tool_call_error(self):
        # Argument validation fails inside the server before any AWS call.
        with self.assertRaises(mcp_client.ToolCallError):
            mcp_client.ask(self.employee.url, "   ")

    def test_responses_are_plain_json_not_an_event_stream(self):
        status, headers, body = _post(self.employee.url, INITIALIZE)
        self.assertEqual(status, 200)
        self.assertTrue(headers["content-type"].startswith("application/json"))
        self.assertEqual(json.loads(body)["result"]["serverInfo"], {"name": "novaops-knowledge-base",
                                                                     "version": "0.2.0"})

    def test_a_forged_host_header_is_rejected(self):
        status, _, _ = _post(self.employee.url, INITIALIZE, Host=f"evil.example:{self.employee.port}")
        self.assertEqual(status, 421)

    def test_a_foreign_origin_is_rejected(self):
        status, _, _ = _post(self.employee.url, INITIALIZE, Origin="http://evil.example")
        self.assertEqual(status, 403)

    def test_no_configuration_value_reaches_responses_headers_or_logs(self):
        result = json.dumps(mcp_client.describe(self.employee.url))
        _, headers, body = _post(self.employee.url, INITIALIZE)
        for text in (result, body, json.dumps(headers), self.employee.output()):
            self.assertNotIn(PLACEHOLDER, text)
        self.assertNotIn("Traceback", self.employee.output())


class UnreachableServerTests(unittest.TestCase):
    def test_nothing_listening_is_one_safe_error(self):
        url = f"http://127.0.0.1:{_free_port()}/mcp"
        for call in (lambda: mcp_client.describe(url), lambda: mcp_client.check_health(url),
                     lambda: mcp_client.ask(url, "q")):
            with self.assertRaises(mcp_client.ServerUnavailableError) as caught:
                call()
            self.assertEqual(caught.exception.kind, "unreachable")
            self.assertIn("Is the MCP server running?", str(caught.exception))

    def test_a_silent_server_times_out_at_the_given_read_timeout(self):
        with socket.socket() as silent:  # accepts connections (backlog) but never answers
            silent.bind(("127.0.0.1", 0))
            silent.listen()
            url = f"http://127.0.0.1:{silent.getsockname()[1]}/mcp"
            started = time.monotonic()
            with self.assertRaises(mcp_client.ServerUnavailableError) as caught:
                mcp_client.describe(url, read_timeout=1)
        self.assertEqual(caught.exception.kind, "timeout")
        self.assertLess(time.monotonic() - started, 15)


if __name__ == "__main__":
    unittest.main()
