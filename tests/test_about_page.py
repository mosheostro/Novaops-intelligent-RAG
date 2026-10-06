"""About / Architecture page: read-only, behind the same gate and navigation as
every other page, and free of backend calls. No AWS calls."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from streamlit.testing.v1 import AppTest  # noqa: E402

from models import CONFIG_NAMES  # noqa: E402
from ui.components import architecture_diagrams as diagrams  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "ui" / "app.py")
ABOUT = "app_pages/about.py"
PAGE_SOURCE = (Path(APP).parent / ABOUT).read_text(encoding="utf-8")


class _AboutTestCase(unittest.TestCase):
    def setUp(self):
        patch.dict(os.environ, {"APP_PASSWORD": "correct horse"}).start()
        patch("ui.access.load_local_env").start()
        patch("ui.access.read_secrets", return_value={}).start()
        self.ask = patch("ask.ask").start()
        self.client = patch("ui.state.opensearch_client").start()
        self.launch = patch("runs.launch_run").start()
        self.runs_dir = Path(tempfile.mkdtemp())
        patch("runs.RUNS_DIR", self.runs_dir).start()
        self.addCleanup(patch.stopall)

    def _about(self, authenticated=True):
        at = AppTest.from_file(APP, default_timeout=30)
        if authenticated:
            at.session_state["authenticated"] = True
        return at.switch_page(ABOUT).run()


class AboutPageTests(_AboutTestCase):
    def test_reachable_through_authenticated_navigation_with_every_section(self):
        at = self._about()
        self.assertFalse(at.exception)
        self.assertEqual([t.value for t in at.main.title], ["NovaOps Intelligent RAG"])
        headers = [h.value for h in at.main.header]
        for section in ("What the system demonstrates", "High-level architecture", "RAG pipeline",
                        "Security vs relevance", "Evaluation", "Live chat vs evaluation runs",
                        "Why Streamlit?", "Current architecture and future extensions",
                        "MCP integration (Stage 1)", "Technology stack", "Architecture principles",
                        "About the author"):
            self.assertIn(section, headers)
        self.assertEqual(len(at.sidebar.radio), 1)  # the shared sidebar (Role) is still there

    def test_opening_the_page_makes_no_backend_calls_and_creates_no_runs(self):
        at = self._about()
        self.assertFalse(at.exception)
        self.ask.assert_not_called()
        self.client.assert_not_called()
        self.launch.assert_not_called()
        self.assertEqual(list(self.runs_dir.iterdir()), [])

    def test_the_author_section_has_clickable_email_and_linkedin(self):
        text = "\n".join(m.value for m in self._about().main.markdown)
        self.assertIn("Moshe Ostrovsky", text)
        self.assertIn("mailto:MosheOstro@gmail.com", text)
        self.assertIn("https://www.linkedin.com/in/moshe-ostrovsky/", text)
        self.assertIn("https://github.com/mosheostro/", text)


class AboutPageGateTests(_AboutTestCase):
    def test_unauthenticated_request_for_the_page_gets_only_the_login_screen(self):
        at = self._about(authenticated=False)
        self.assertFalse(at.exception)
        self.assertEqual(len(at.text_input), 1)          # the password field
        self.assertEqual(len(at.header), 0)              # none of the About sections
        self.assertEqual(len(at.sidebar.radio), 0)


class DiagramContentTests(unittest.TestCase):
    def test_every_diagram_is_a_mermaid_flowchart(self):
        for name, body in diagrams.ALL.items():
            with self.subTest(diagram=name):
                first = [line for line in body.splitlines() if not line.startswith("%%")][0]
                self.assertTrue(first.startswith("flowchart"), name)

    def test_extensions_diagram_shows_mcp_stage_1_as_implemented_and_the_api_as_future(self):
        body = diagrams.EXTENSIONS
        self.assertIn("Streamlit UI<br/>implemented", body)
        self.assertIn("MCP server / tools<br/>implemented · Stage 1 · STDIO", body)
        self.assertIn("HTTP API<br/>future extension point", body)
        self.assertNotIn("planned", body)

    def test_mcp_is_described_as_implemented_not_planned(self):
        self.assertIn("MCP server<br/>STDIO · Stage 1", diagrams.ARCHITECTURE)
        self.assertNotRegex(diagrams.ARCHITECTURE, r"MCP[^\n]*future")
        self.assertIn("MCP — Stage 1 implemented (STDIO)", PAGE_SOURCE)
        self.assertNotIn("MCP — planned", PAGE_SOURCE)
        self.assertNotIn("Future MCP integration", PAGE_SOURCE)

    def test_evaluation_diagram_shows_all_five_configurations_without_a_winner(self):
        for name in CONFIG_NAMES:
            self.assertIn(name, diagrams.EVALUATION)
        for text in [*diagrams.ALL.values(), PAGE_SOURCE]:
            self.assertNotRegex(text.lower(), r"\b(best|winner)\b")

    def test_page_reads_nothing_at_runtime_from_runs_or_the_backend(self):
        import re
        imported = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", PAGE_SOURCE, re.M))
        self.assertEqual(imported - {"streamlit", "ui.components"}, set())  # only the static diagrams
        self.assertNotIn("session_state", PAGE_SOURCE)


if __name__ == "__main__":
    unittest.main()
