"""DEFAULT_CONFIG — the one shared default configuration (models.py) that Chat
and the future MCP layer both use. Static checks plus a fresh-interpreter import;
no AWS, OpenSearch, Bedrock, Streamlit runtime or MCP."""
import ast
import subprocess
import sys
import unittest
from pathlib import Path
from typing import get_args

from models import CONFIG_NAMES, DEFAULT_CONFIG, ConfigName

ROOT = Path(__file__).resolve().parent.parent
CHAT = ROOT / "ui" / "app_pages" / "chat.py"
CANONICAL_CONFIGS = ("baseline", "filter-only", "rerank-only", "filter + rerank static", "filter + rerank dynamic")


class DefaultConfigTests(unittest.TestCase):
    def test_default_is_filter_rerank_dynamic(self):
        self.assertEqual(DEFAULT_CONFIG, "filter + rerank dynamic")

    def test_default_is_a_canonical_configuration(self):
        self.assertIn(DEFAULT_CONFIG, CONFIG_NAMES)

    def test_configuration_names_are_unchanged(self):
        self.assertEqual(CONFIG_NAMES, CANONICAL_CONFIGS)
        self.assertEqual(get_args(ConfigName), CANONICAL_CONFIGS)

    def test_importing_models_loads_no_other_project_module(self):
        # A fresh interpreter, so modules already imported by other tests cannot hide a cycle.
        project = sorted(p.stem for p in ROOT.glob("*.py"))
        code = ("import sys, models; "
                f"print(','.join(sorted(m for m in {project!r} if m in sys.modules)))")
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "models")


class ChatUsesSharedDefaultTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(CHAT.read_text(encoding="utf-8"))

    def test_chat_does_not_repeat_the_default_literal(self):
        literals = [n.value for n in ast.walk(self.tree) if isinstance(n, ast.Constant)]
        self.assertNotIn(DEFAULT_CONFIG, literals)

    def test_chat_imports_the_default_from_models(self):
        imported = {alias.name for n in ast.walk(self.tree)
                    if isinstance(n, ast.ImportFrom) and n.module == "models" for alias in n.names}
        self.assertIn("DEFAULT_CONFIG", imported)

    def test_chat_preselects_the_shared_default(self):
        calls = [ast.unparse(n) for n in ast.walk(self.tree) if isinstance(n, ast.Call)]
        self.assertIn("CONFIG_NAMES.index(DEFAULT_CONFIG)", calls)


if __name__ == "__main__":
    unittest.main()
