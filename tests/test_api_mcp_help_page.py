"""API & MCP Help page: a static user manual for the REST API and the MCP server.
Behind the same gate and navigation as every other page, it makes no backend,
HTTP or MCP call and imports no client — and what it shows is checked against
the real contracts: REST paths against the OpenAPI document, MCP names against
the recorded contract snapshot, every command against the real argument parser,
and every URL's port against the port that command really uses. No AWS calls.
"""
import ast
import importlib.util
import json
import os
import re
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "ui" / "app.py")
PAGE = "app_pages/api_mcp_help.py"
PAGE_SOURCE = (ROOT / "ui" / PAGE).read_text(encoding="utf-8")
SNAPSHOT = json.loads((ROOT / "tests" / "fixtures" / "mcp_contract_snapshot.json").read_text(encoding="utf-8"))
SECTIONS = ("Before you start", "REST API", "MCP server", "REST or MCP?", "Troubleshooting",
            "Where the contracts live")
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
HAS_MCP = importlib.util.find_spec("mcp") is not None


class _PageTestCase(unittest.TestCase):
    def setUp(self):
        patch.dict(os.environ, {"APP_PASSWORD": "correct horse", "OPENSEARCH_COLLECTION": "SECRET-COLLECTION"}).start()
        patch("ui.access.load_local_env").start()
        patch("ui.access.read_secrets", return_value={}).start()
        self.backend = [patch(target).start() for target in
                        ("ask.ask", "ui.state.opensearch_client", "client.opensearch_client", "manage.aoss_client",
                         "manage.collection_health", "runs.launch_run")]
        self.runs_dir = Path(tempfile.mkdtemp())
        patch("runs.RUNS_DIR", self.runs_dir).start()
        self.addCleanup(patch.stopall)

    def _page(self, authenticated=True):
        at = AppTest.from_file(APP, default_timeout=30)
        if authenticated:
            at.session_state["authenticated"] = True
        return at.switch_page(PAGE).run()


def _rendered_text(at) -> str:
    parts = [e.value for kind in ("markdown", "caption", "code", "info", "title", "header", "subheader")
             for e in getattr(at.main, kind)]
    parts += [str(e.value) for e in at.main.table]
    return "\n".join(str(p) for p in parts)


def _commands(at) -> list[tuple[list[str], str]]:
    """Every `python …` and `npx …` command shown in the page's code blocks, split like
    a shell would, paired with its trailing `# comment` (which may carry the URL).
    Shell-specific lines (pip, curl, PowerShell) are not parsed."""
    commands = []
    for block in at.main.code:
        for line in block.value.splitlines():
            line = line.strip()
            if not line.startswith(("python ", "npx ")):
                continue
            command, _, comment = line.partition("  #")
            commands.append((shlex.split(command, posix=True), comment.strip()))
    return commands


class HelpPageTests(_PageTestCase):
    def test_reachable_through_authenticated_navigation_with_every_section(self):
        at = self._page()
        self.assertFalse(at.exception)
        self.assertEqual([t.value for t in at.main.title], ["API & MCP Help"])
        headers = [h.value for h in at.main.header]
        for section in SECTIONS:
            self.assertIn(section, headers)
        self.assertEqual(len(at.sidebar.radio), 1)  # the shared sidebar (Role) is still there
        self.assertIn("Help", [e.label for e in at.sidebar.expander])  # usage help stays in the sidebar

    def test_registered_right_after_the_mcp_server_page_and_before_about(self):
        source = Path(APP).read_text(encoding="utf-8")
        self.assertIn(f'st.Page("{PAGE}", title="API & MCP Help"', source)
        self.assertLess(source.index('"app_pages/mcp_page.py"'), source.index(f'"{PAGE}"'))
        self.assertLess(source.index(f'"{PAGE}"'), source.index('"app_pages/about.py"'))
        between = source[source.index('"app_pages/mcp_page.py"'):source.index(f'"{PAGE}"')]
        self.assertEqual(between.count("st.Page("), 1)  # only this page's own entry: immediately after

    def test_unauthenticated_request_gets_only_the_login_screen(self):
        at = self._page(authenticated=False)
        self.assertFalse(at.exception)
        self.assertEqual(len(at.text_input), 1)  # the password field
        self.assertEqual(len(at.header), 0)
        self.assertEqual(len(at.sidebar.radio), 0)

    def test_opening_the_page_calls_no_backend_and_creates_no_runs(self):
        self.assertFalse(self._page().exception)
        for mock in self.backend:
            mock.assert_not_called()
        self.assertEqual(list(self.runs_dir.iterdir()), [])

    def test_the_page_says_it_is_a_manual_and_where_commands_run(self):
        text = _rendered_text(self._page())
        self.assertIn("your own machine", text)
        self.assertIn("does not connect", text)
        self.assertIn("MCP server page", text)
        self.assertIn("built-in demo client", text)

    def test_no_infrastructure_identifier_is_shown(self):
        text = _rendered_text(self._page()).lower()
        import client
        import config
        for value in ("secret-collection", client.INDEX_NAME, config.BEDROCK_MODEL_ID.lower(),
                      config.BEDROCK_EMBEDDING_MODEL_ID.lower(), "amazonaws", "arn:", "aoss", "us-east", "eu-west"):
            with self.subTest(value=value):
                self.assertNotIn(value.lower(), text)


class StaticManualTests(unittest.TestCase):
    """Documentation only: no client, no process, no state."""

    def test_the_page_imports_only_streamlit(self):
        imported = set()
        for node in ast.walk(ast.parse(PAGE_SOURCE)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertEqual(imported, {"streamlit"})
        for forbidden in ("api_server", "mcp_server", "mcp_client", "mcp", "httpx", "httpx2", "requests", "urllib",
                          "subprocess", "socket", "ask", "client", "manage"):
            self.assertNotIn(forbidden, imported)

    def test_no_session_state(self):
        self.assertNotIn("session_state", PAGE_SOURCE)


class ContractAccuracyTests(_PageTestCase):
    """What the page shows must match the real interfaces."""

    def setUp(self):
        super().setUp()
        at = self._page()
        self.assertFalse(at.exception)
        self.text = _rendered_text(at)
        self.commands = _commands(at)

    def _scripts(self, script):
        """(argv, comment) for every `python <script> …` line."""
        return [(argv[2:], comment) for argv, comment in self.commands if argv[:2] == ["python", script]]

    @unittest.skipUnless(HAS_FASTAPI, "needs the optional REST dependency: pip install -r requirements-api.txt")
    def test_every_rest_path_shown_is_served_by_the_api(self):
        import api_server
        app = api_server.build_app("employee")
        served = set(app.openapi()["paths"]) | {app.docs_url, app.openapi_url}
        shown = set(re.findall(r"/(?:v1/[a-z_]+|healthz|docs|openapi\.json)\b", self.text))
        self.assertGreaterEqual(shown, {"/v1/ask", "/v1/health", "/healthz", "/docs", "/openapi.json"})
        self.assertEqual(shown - served, set())

    def test_every_mcp_tool_and_resource_shown_is_in_the_published_contract(self):
        tools = set(SNAPSHOT["tools"])
        resources = {r["uri"] for r in SNAPSHOT["resources"]}
        for tool in tools:
            self.assertIn(tool, self.text)  # the whole surface is described
        named = {c[c.index("--tool-name") + 1] for c, _ in self.commands if "--tool-name" in c}
        self.assertTrue(named)
        self.assertEqual(named - tools, set())
        self.assertEqual(set(re.findall(r"rag://[a-z_]+", self.text)) - resources, set())
        for command, _ in self.commands:
            if "--tool-arg" in command:
                name = command[command.index("--tool-arg") + 1].split("=", 1)[0]
                tool = command[command.index("--tool-name") + 1]
                self.assertIn(name, SNAPSHOT["tools"][tool]["input_schema"]["properties"])

    @unittest.skipUnless(HAS_FASTAPI, "needs the optional REST dependency: pip install -r requirements-api.txt")
    def test_rest_start_commands_parse_and_their_urls_use_the_real_port(self):
        import api_server
        commands = self._scripts("api_server.py")
        self.assertEqual(len(commands), 2)
        ports = {}
        for argv, comment in commands:
            with patch("api_server.uvicorn.run") as run:
                api_server.main(argv)
            role = argv[argv.index("--role") + 1]
            ports[role] = run.call_args.kwargs["port"]
            self.assertEqual(urlsplit(comment).port, ports[role])
        self.assertEqual(ports, {"employee": api_server.DEFAULT_PORT, "manager": 8002})
        self.assertEqual(api_server.DEFAULT_PORT, 8001)

    @unittest.skipUnless(HAS_MCP, "needs the optional MCP dependency: pip install -r requirements-mcp.txt")
    def test_mcp_start_commands_parse_and_their_urls_use_the_real_port(self):
        import mcp_server
        commands = self._scripts("mcp_server.py")
        self.assertEqual(len(commands), 2)
        ports = {}
        for argv, comment in commands:
            with patch.object(mcp_server.MCPServer, "run") as run:
                mcp_server.main(argv)
            self.assertEqual(run.call_args.args[0], "streamable-http")
            role = argv[argv.index("--role") + 1]
            ports[role] = run.call_args.kwargs["port"]
            self.assertEqual(urlsplit(comment).port, ports[role])
            self.assertEqual(urlsplit(comment).path, mcp_server.HTTP_PATH)
        self.assertEqual(ports, {"employee": 8000, "manager": 8010})

    @unittest.skipUnless(HAS_MCP, "needs the optional MCP dependency: pip install -r requirements-mcp.txt")
    def test_mcp_client_commands_parse_and_point_at_a_server_the_page_starts(self):
        import mcp_client
        commands = self._scripts("mcp_client.py")
        self.assertGreaterEqual(len(commands), 3)
        for argv, _ in commands:
            args = mcp_client._parser().parse_args(argv)  # raises SystemExit on any unknown or missing option
            if getattr(args, "url", None):
                mcp_client.check_url(args.url)
                self.assertEqual(urlsplit(args.url).port, 8000)

    def test_inspector_commands_use_the_verified_cli_form(self):
        inspector = [c for c, _ in self.commands if c[:2] == ["npx", "@modelcontextprotocol/inspector"]]
        cli = [c for c in inspector if "--cli" in c]
        self.assertTrue(cli)
        self.assertEqual(len(inspector) - len(cli), 1)  # plus the one web-UI launch
        for command in cli:
            self.assertEqual(command[2], "--cli")  # mode flag first (Inspector 2.9.0)
            self.assertEqual(command[3], "http://127.0.0.1:8000/mcp")  # Streamable HTTP target only
            self.assertIn(command[command.index("--method") + 1],
                          {"tools/list", "tools/call", "resources/list", "resources/read"})
        self.assertIn("2.9.0", self.text)  # the version the examples were verified with


if __name__ == "__main__":
    unittest.main()
