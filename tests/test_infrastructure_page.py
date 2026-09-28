"""Infrastructure & Setup page: read-only, static, behind the same gate and
navigation as every other page, placed before About / Architecture, and free
of backend calls and private infrastructure details. No AWS calls."""
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from streamlit.testing.v1 import AppTest  # noqa: E402

from ui.components import infrastructure_diagrams as diagrams  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "ui" / "app.py")
PAGE = "app_pages/infrastructure.py"
PAGE_SOURCE = (Path(APP).parent / PAGE).read_text(encoding="utf-8")
SECTIONS = ("Setup lifecycle", "Knowledge-base ingestion", "Index fields and filtering",
            "Supporting scripts", "Safeguards")


class _PageTestCase(unittest.TestCase):
    def setUp(self):
        patch.dict(os.environ, {"APP_PASSWORD": "correct horse", "OPENSEARCH_COLLECTION": "SECRET-COLLECTION"}).start()
        patch("ui.access.load_local_env").start()
        patch("ui.access.read_secrets", return_value={}).start()
        self.ask = patch("ask.ask").start()
        self.client = patch("ui.state.opensearch_client").start()
        self.os_client = patch("client.opensearch_client").start()
        self.launch = patch("runs.launch_run").start()
        self.runs_dir = Path(tempfile.mkdtemp())
        patch("runs.RUNS_DIR", self.runs_dir).start()
        self.addCleanup(patch.stopall)

    def _page(self, authenticated=True):
        at = AppTest.from_file(APP, default_timeout=30)
        if authenticated:
            at.session_state["authenticated"] = True
        return at.switch_page(PAGE).run()


class InfrastructurePageTests(_PageTestCase):
    def test_reachable_through_authenticated_navigation_with_every_section(self):
        at = self._page()
        self.assertFalse(at.exception)
        self.assertEqual([t.value for t in at.main.title], ["Infrastructure & Setup"])
        headers = [h.value for h in at.main.header]
        for section in SECTIONS:
            self.assertIn(section, headers)
        self.assertEqual(len(at.sidebar.radio), 1)            # shared sidebar (Role) still there
        self.assertIn("Help", [e.label for e in at.sidebar.expander])  # Help stays a sidebar panel

    def test_opening_the_page_makes_no_backend_calls_and_creates_no_runs(self):
        self.assertFalse(self._page().exception)
        for mock in (self.ask, self.client, self.os_client, self.launch):
            mock.assert_not_called()
        self.assertEqual(list(self.runs_dir.iterdir()), [])

    def test_snapshot_numbers_are_shown_and_labelled_as_a_documented_snapshot(self):
        at = self._page()
        metrics = {m.label: m.value for m in at.main.metric}
        self.assertEqual(metrics["Documents"], "32")
        self.assertEqual(metrics["Chunks"], "400")
        text = "\n".join(c.value for c in at.main.caption)
        self.assertIn("documented", text.lower())

    def test_no_private_infrastructure_details_are_rendered(self):
        at = self._page()
        rendered = "\n".join(str(e.value) for kind in ("markdown", "caption", "metric", "header", "title", "info")
                             for e in getattr(at.main, kind))
        rendered += "\n".join(diagrams.ALL.values()) + PAGE_SOURCE
        for secret in ("SECRET-COLLECTION", "novaops-rag", "REMOVE", "us-east-1", "amazonaws.com",
                       "OPENSEARCH_COLLECTION", "AWS_ACCESS_KEY", "AWS_SECRET", "APP_PASSWORD", ".env",
                       "endpoint"):
            self.assertNotIn(secret, rendered)
        self.assertIsNone(re.search(r"\b\d{12}\b", rendered))  # no AWS account ids


class NavigationTests(unittest.TestCase):
    def test_page_sits_before_about_architecture_in_the_navigation(self):
        source = Path(APP).read_text(encoding="utf-8")
        self.assertLess(source.index('"app_pages/infrastructure.py"'), source.index('"app_pages/about.py"'))

    def test_unauthenticated_request_gets_only_the_login_screen(self):
        with patch.dict(os.environ, {"APP_PASSWORD": "correct horse"}), \
                patch("ui.access.load_local_env"), patch("ui.access.read_secrets", return_value={}):
            at = AppTest.from_file(APP, default_timeout=30)
            at.switch_page(PAGE).run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.text_input), 1)              # the password field
        self.assertEqual(len(at.header), 0)
        self.assertNotIn("Infrastructure & Setup", [t.value for t in at.title])


class ContentTests(unittest.TestCase):
    def test_every_diagram_is_a_mermaid_flowchart(self):
        for name, body in diagrams.ALL.items():
            with self.subTest(diagram=name):
                first = [line for line in body.splitlines() if not line.startswith("%%")][0]
                self.assertTrue(first.startswith("flowchart"), name)

    def test_provisioning_is_described_as_outside_this_repository(self):
        self.assertIn("outside this repository", diagrams.LIFECYCLE)
        self.assertNotRegex((diagrams.LIFECYCLE + PAGE_SOURCE).lower(), r"creates? the collection")

    def test_collection_administration_is_separate_from_the_setup_flow(self):
        self.assertNotIn("manage.py", diagrams.LIFECYCLE)
        self.assertIn("manage.py", diagrams.ADMINISTRATION)
        for step in ("create_index.py", "ingest.py", "runtime"):
            self.assertNotIn(step, diagrams.ADMINISTRATION)
        self.assertIn("confirmation", diagrams.ADMINISTRATION)

    def test_page_is_static_and_imports_only_streamlit_and_ui_components(self):
        imported = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", PAGE_SOURCE, re.M))
        self.assertEqual(imported - {"streamlit", "ui.components"}, set())
        self.assertNotIn("session_state", PAGE_SOURCE)


if __name__ == "__main__":
    unittest.main()
