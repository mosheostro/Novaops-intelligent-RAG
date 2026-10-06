"""The dashboard's MCP server page: an MCP client/demo surface over mcp_client's
synchronous facade. The facade is patched — no MCP server, no network, no AWS. The
missing-dependency test runs without the optional `mcp` package; the rest need it
(they build real MCP projections as fixtures)."""
import ast
import importlib.util
import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "ui" / "app.py")
PAGE = "app_pages/mcp_page.py"
PAGE_SOURCE = (ROOT / "ui" / PAGE).read_text(encoding="utf-8")
HAS_MCP = importlib.util.find_spec("mcp") is not None
URL = "http://127.0.0.1:8000/mcp"


def _texts(at) -> str:
    return "\n".join(str(e.value) for kind in ("title", "header", "subheader", "markdown", "caption", "error",
                                               "warning", "info", "success", "metric", "code")
                     for e in getattr(at, kind))


class _PageTestCase(unittest.TestCase):
    def setUp(self):
        patch.dict(os.environ, {"APP_PASSWORD": "correct horse"}).start()
        patch("ui.access.load_local_env").start()
        patch("ui.access.read_secrets", return_value={}).start()
        self.rag_ask = patch("ask.ask").start()  # the page must never call the RAG directly
        self.addCleanup(patch.stopall)

    def _page(self, authenticated=True):
        at = AppTest.from_file(APP, default_timeout=30)
        if authenticated:
            at.session_state["authenticated"] = True
        return at.switch_page(PAGE).run()


class MissingDependencyTests(_PageTestCase):
    def test_without_the_mcp_client_the_page_explains_how_to_install_it(self):
        with patch.dict(sys.modules, {"mcp_client": None}):  # `import mcp_client` raises ImportError
            at = self._page()
        self.assertFalse(at.exception)
        text = _texts(at)
        self.assertIn("pip install -r requirements-mcp.txt", text)
        self.assertEqual(len(at.button), 0)  # nothing to connect with
        self.assertEqual(len(at.sidebar.radio), 1)  # the rest of the dashboard still works


class PageSourceTests(unittest.TestCase):
    def test_the_page_imports_only_the_client_facade_never_mcp_anyio_the_server_or_the_rag(self):
        tree = ast.parse(PAGE_SOURCE)
        imported = {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
        imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        roots = {name.split(".")[0] for name in imported}
        self.assertIn("mcp_client", roots)
        for forbidden in ("mcp", "anyio", "httpx2", "mcp_server", "ask", "retrieval", "client", "subprocess"):
            self.assertNotIn(forbidden, roots)

    def test_the_page_is_registered_in_the_navigation(self):
        app_source = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
        self.assertIn(f'st.Page("{PAGE}", title="MCP server"', app_source)


@unittest.skipUnless(HAS_MCP, "needs the optional dependency: pip install -r requirements-mcp.txt")
class McpPageTests(_PageTestCase):
    def setUp(self):
        super().setUp()
        import mcp_client
        import mcp_server
        from tests.test_mcp_server import JUDGEMENT, _ask_result, _health
        self.mcp_client, self.mcp_server = mcp_client, mcp_server
        self.projection = lambda **kw: mcp_server.project_ask_result(_ask_result(**kw)).model_dump(mode="json")
        self.judgement = JUDGEMENT
        self.describe = patch("mcp_client.describe", return_value=self._described("employee")).start()
        self.check_health = patch("mcp_client.check_health", return_value=mcp_server.project_health(
            _health()).model_dump(mode="json")).start()
        self.ask = patch("mcp_client.ask", return_value=self.projection()).start()

    def _described(self, role):
        return {"server": {"name": "novaops-knowledge-base", "version": "1.0"}, "transport": "streamable-http",
                "tools": ["ask_rag", "get_rag_capabilities", "health_check"], "resources": ["rag://subjects"],
                "capabilities": self.mcp_server.build_capabilities(role).model_dump(mode="json"),
                "subjects": ["benefits", "time_off"]}

    def _connected(self, url=URL):
        at = self._page()
        at.text_input(key="mcp_url").set_value(url)
        return at.button(key="mcp_connect").click().run()

    def _asked(self, question="How does PTO accrue?", **form):
        at = self._connected()
        at.text_area(key="mcp_question").set_value(question)
        if "config" in form:
            at.selectbox(key="mcp_config").set_value(form["config"])
        if "judge" in form:
            at.toggle(key="mcp_judge").set_value(form["judge"])
        if "cutoff" in form:
            at.date_input(key="mcp_cutoff").set_value(form["cutoff"])
        return at.button(key="mcp_ask_submit").click().run()

    # --- gate and page open -----------------------------------------------------------------

    def test_unauthenticated_request_gets_only_the_login_screen(self):
        at = self._page(authenticated=False)
        self.assertFalse(at.exception)
        self.assertEqual(len(at.text_input), 1)  # the password field
        self.assertNotIn("MCP server", [t.value for t in at.title])
        self.describe.assert_not_called()

    def test_opening_the_page_calls_nothing(self):
        at = self._page()
        self.assertFalse(at.exception)
        self.assertEqual([t.value for t in at.title], ["MCP server"])
        self.assertEqual(at.text_input(key="mcp_url").value, URL)
        for mock in (self.describe, self.check_health, self.ask, self.rag_ask):
            mock.assert_not_called()
        self.assertNotIn("Ask through MCP", [h.value for h in at.subheader])  # nothing to ask before connecting

    # --- connect and discovery ------------------------------------------------------------

    def test_connect_discovers_and_shows_the_surface(self):
        at = self._connected()
        self.assertFalse(at.exception)
        self.describe.assert_called_once_with(URL, read_timeout=120)
        text = _texts(at)
        for expected in ("Connected", "streamable-http", "novaops-knowledge-base", "1.0", "employee",
                         "ask_rag", "get_rag_capabilities", "health_check", "rag://subjects",
                         "benefits", "time_off", "does not control"):
            self.assertIn(expected, text)
        self.assertTrue(any("contract_version" in str(j.value) for j in at.get("json")))  # capabilities
        self.check_health.assert_not_called()
        self.ask.assert_not_called()

    def test_discovery_is_kept_across_reruns_without_calling_again(self):
        at = self._connected()
        at.run()
        self.describe.assert_called_once()
        self.assertIn("novaops-knowledge-base", _texts(at))

    def test_role_mismatch_is_informational(self):
        self.describe.return_value = self._described("manager")
        at = self._connected()  # sidebar role defaults to employee
        infos = "\n".join(i.value for i in at.info)
        self.assertIn("sidebar role is employee", infos)
        self.assertIn("started as manager", infos)
        self.assertFalse(at.error)
        at.sidebar.radio(key="role").set_value("manager").run()
        self.assertNotIn("sidebar role is", "\n".join(i.value for i in at.info))

    def test_unreachable_server_is_a_safe_warning_with_the_start_hint(self):
        self.describe.side_effect = self.mcp_client.ServerUnavailableError(
            "unreachable", "could not connect to 127.0.0.1:8000 (connection refused or unknown host). "
                           "Is the MCP server running?")
        at = self._connected()
        self.assertFalse(at.exception)
        warnings = "\n".join(w.value for w in at.warning)
        self.assertIn("MCP server unavailable", warnings)
        self.assertIn("could not connect to 127.0.0.1:8000", warnings)
        self.assertIn("python mcp_server.py --transport streamable-http --role employee", _texts(at))
        self.assertNotIn("Connected", _texts(at))

    def test_invalid_or_non_loopback_urls_are_refused_without_calling_the_server(self):
        for url, expected in (("127.0.0.1:8000", "must start with http://"),
                              ("http://127.0.0.1:8000", "the endpoint path is missing"),
                              ("http://example.com:8000/mcp", "only a local MCP server"),
                              ("http://0.0.0.0:8000/mcp", "only a local MCP server"),
                              ("http://127.0.0.2:8000/mcp", "only a local MCP server"),
                              ("http://localhost.evil.example:8000/mcp", "only a local MCP server"),
                              ("http://127.0.0.1@evil.example:8000/mcp", "only a local MCP server")):
            with self.subTest(url=url):
                at = self._connected(url)
                self.assertFalse(at.exception)
                self.assertIn(expected, "\n".join(e.value for e in at.error))
        self.describe.assert_not_called()

    def test_loopback_urls_are_accepted(self):
        for url in ("http://127.0.0.1:8001/mcp", "http://localhost:8000/mcp", "http://[::1]:8000/mcp"):
            with self.subTest(url=url):
                self._connected(url)
                self.assertEqual(self.describe.call_args.args, (url,))

    def test_an_unexpected_error_is_a_generic_message_never_a_traceback(self):
        self.describe.side_effect = ExceptionGroup("unhandled errors in a TaskGroup", [ValueError("SECRET bug")])
        with self.assertLogs("ui.app_pages.mcp_page", level="ERROR") as logs:  # full detail stays in the log
            at = self._connected()
        self.assertFalse(at.exception)
        errors = "\n".join(e.value for e in at.error)
        self.assertIn("Unexpected error while communicating with the MCP server.", errors)
        for leak in ("SECRET", "ExceptionGroup", "ValueError", "Traceback"):
            self.assertNotIn(leak, _texts(at))
        self.assertIn("SECRET bug", "\n".join(logs.output))

    # --- health ---------------------------------------------------------------------------

    def test_health_check_is_explicit_and_shows_the_projection(self):
        at = self._connected()
        self.check_health.assert_not_called()
        at.button(key="mcp_health").click().run()
        self.check_health.assert_called_once_with(URL, read_timeout=120)
        metrics = {m.label: m.value for m in at.metric}
        self.assertEqual(metrics["Ready"], "Yes")
        self.assertEqual(metrics["Collection state"], "ACTIVE")
        self.assertIn("Chunks", metrics)

    # --- ask through MCP -------------------------------------------------------------------

    def test_ask_goes_through_the_mcp_client_with_the_form_values(self):
        at = self._asked(config="baseline", judge=True, cutoff=date(2025, 1, 31))
        self.assertFalse(at.exception)
        self.ask.assert_called_once_with(URL, "How does PTO accrue?", config="baseline", judge=True,
                                         updated_on_or_after=date(2025, 1, 31), read_timeout=120)
        self.rag_ask.assert_not_called()

    def test_configurations_come_from_the_servers_capabilities(self):
        at = self._connected()
        select = at.selectbox(key="mcp_config")
        self.assertEqual(select.options, [c["name"] for c in self._described("employee")["capabilities"]
                                          ["configurations"]])
        self.assertEqual(select.value, "filter + rerank dynamic")

    def test_answer_status_sources_and_raw_response_are_rendered(self):
        self.ask.return_value = self.projection(judgement=self.judgement)
        at = self._asked()
        text = _texts(at)
        self.assertIn("SENTINEL-GENERATED-ANSWER", text)
        self.assertIn("pto.md", str(at.dataframe[0].value))
        self.assertIn("selected", text)
        self.assertEqual(len(at.dataframe), 1)  # sources
        self.assertIn("Faithfulness", [m.label for m in at.metric])
        self.assertIn("Raw MCP response", [e.label for e in at.expander])
        self.assertTrue(any("security_audit" in str(j.value) for j in at.get("json")))

    def test_a_security_violation_withholds_answer_sources_and_judgement(self):
        self.ask.return_value = self.projection(violation=True, judgement=self.judgement)
        at = self._asked()
        self.assertFalse(at.exception)
        errors = "\n".join(e.value for e in at.error)
        self.assertIn(self.mcp_server.SECURITY_VIOLATION_EXPLANATION, errors)
        self.assertEqual(len(at.dataframe), 0)
        self.assertNotIn("Faithfulness", [m.label for m in at.metric])
        self.assertNotIn("SENTINEL", _texts(at))  # nothing of the generated answer or of any source

    def test_not_found_is_a_normal_result_not_an_error(self):
        self.ask.return_value = self.projection(status="not_found")
        at = self._asked()
        self.assertFalse(at.exception)
        self.assertFalse(at.error)
        self.assertIn("not_found", _texts(at))
        self.assertTrue(at.info)

    def test_a_tool_error_shows_the_servers_safe_message(self):
        self.ask.side_effect = self.mcp_client.ToolCallError(
            "Error executing tool ask_rag: service_unavailable: the knowledge base or model service is unavailable.")
        at = self._asked()
        self.assertFalse(at.exception)
        self.assertIn("service_unavailable", "\n".join(e.value for e in at.error))

    def test_a_server_that_went_away_between_connect_and_ask_is_a_safe_warning(self):
        self.ask.side_effect = self.mcp_client.ServerUnavailableError("dropped", "the connection to "
                                                                                 f"{URL} was closed unexpectedly")
        at = self._asked()
        self.assertFalse(at.exception)
        self.assertIn("MCP server unavailable", "\n".join(w.value for w in at.warning))

    def test_the_question_is_limited_to_the_servers_maximum(self):
        at = self._connected()
        self.assertEqual(at.text_area(key="mcp_question").max_chars, self.mcp_server.MAX_QUESTION_CHARS)


@unittest.skipUnless(HAS_MCP, "needs the optional dependency: pip install -r requirements-mcp.txt")
class RealServerTests(_PageTestCase):
    """The page against a real server process over real HTTP — nothing of the client patched.
    Proves the synchronous facade (anyio.run) works from Streamlit's script thread."""

    def test_connect_discovers_a_real_manager_server(self):
        from tests.test_mcp_http import _HttpServer
        server = _HttpServer("manager")
        self.addCleanup(server.stop)
        at = self._page()
        at.text_input(key="mcp_url").set_value(server.url)
        at.button(key="mcp_connect").click().run()
        self.assertFalse(at.exception)
        text = _texts(at)
        self.assertIn("Connected", text)
        self.assertIn("novaops-knowledge-base", text)
        self.assertIn("version `0.2.0`", text)
        self.assertIn("started as manager", " ".join(i.value for i in at.info))
        self.assertEqual(at.selectbox(key="mcp_config").value, "filter + rerank dynamic")
        self.rag_ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
