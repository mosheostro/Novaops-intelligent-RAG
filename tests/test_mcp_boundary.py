"""The MCP dependency boundary: MCP is an optional adapter, never a dependency of
the RAG application. Static checks only — requirement files are read as text and
modules are parsed with ast, never imported — so these tests need neither the
`mcp` package nor AWS, OpenSearch, Bedrock or a Streamlit runtime.

Scanned: the project's own Python modules (root and ui/). Skipped: tests/,
hidden directories (.venv, .git, .idea, ...), caches, git-ignored generated or
third-party folders (runs/, logs/, reference/). The two MCP adapters — the
server (mcp_server.py) and the demo client (mcp_client.py) — are the only modules
that may import `mcp`; nothing may import either of them.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIPPED_DIRS = {"tests", "__pycache__", "runs", "logs", "reference"}
MCP_ADAPTERS = frozenset({"mcp_server.py", "mcp_client.py"})  # the only modules allowed to import `mcp`


def _requirement_lines(path: Path) -> list[str]:
    """Non-empty requirement lines with comments removed."""
    lines = (line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line]


def _project_modules() -> list[Path]:
    modules = []
    for path in ROOT.rglob("*.py"):
        parts = path.relative_to(ROOT).parts[:-1]
        if any(part.startswith(".") or part in SKIPPED_DIRS for part in parts):
            continue
        modules.append(path)
    return sorted(modules)


def _imported_modules(source: str) -> set[str]:
    """Absolute module names a source imports (`import x.y`, `from x.y import z`),
    at any nesting level — a function-local import counts too."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def _imports_package(source: str, package: str) -> bool:
    return any(name == package or name.startswith(package + ".") for name in _imported_modules(source))


class RequirementFilesTests(unittest.TestCase):
    def test_main_requirements_do_not_include_mcp(self):
        names = [re.match(r"[A-Za-z0-9_.-]+", line).group(0).lower()
                 for line in _requirement_lines(ROOT / "requirements.txt") if not line.startswith("-")]
        self.assertTrue(names)  # the file was actually read
        self.assertNotIn("mcp", names)

    def test_mcp_requirements_extend_the_main_requirements_with_the_pinned_sdk(self):
        self.assertEqual(_requirement_lines(ROOT / "requirements-mcp.txt"),
                         ["-r requirements.txt", "mcp>=2.3,<3"])


class ImportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.modules = _project_modules()

    def test_scan_covers_the_project_and_skips_tests_and_environments(self):
        scanned = {path.relative_to(ROOT).as_posix() for path in self.modules}
        for expected in ("ask.py", "retrieval.py", "models.py", "manage.py", "ui/app.py"):
            self.assertIn(expected, scanned)
        self.assertFalse([p for p in scanned if p.startswith(("tests/", ".venv/", "reference/"))])

    def _offenders(self, package: str, allowed: frozenset[str] = frozenset()) -> list[str]:
        return [path.relative_to(ROOT).as_posix() for path in self.modules
                if path.name not in allowed and _imports_package(path.read_text(encoding="utf-8"), package)]

    def test_no_module_except_the_mcp_adapters_imports_mcp(self):
        self.assertEqual(self._offenders("mcp", allowed=MCP_ADAPTERS), [])

    def test_no_module_imports_the_mcp_server(self):
        self.assertEqual(self._offenders("mcp_server"), [])

    def test_no_module_imports_the_mcp_client(self):
        self.assertEqual(self._offenders("mcp_client"), [])


class ImportDetectionTests(unittest.TestCase):
    """The detector itself, so a passing boundary test cannot be a blind one."""

    def test_detects_every_absolute_import_form_including_nested_ones(self):
        for source in ("import mcp", "import mcp.server as s", "from mcp.server.mcpserver import MCPServer",
                       "from mcp import types", "def f():\n    import mcp\n"):
            with self.subTest(source=source):
                self.assertTrue(_imports_package(source, "mcp"))
        self.assertTrue(_imports_package("from mcp_server import main", "mcp_server"))
        self.assertTrue(_imports_package("import mcp_server", "mcp_server"))

    def test_ignores_similarly_named_and_relative_imports(self):
        for source in ("import mcpx", "import mcp_server", "from mcp_tools import x", "from . import mcp"):
            with self.subTest(source=source):
                self.assertFalse(_imports_package(source, "mcp"))


if __name__ == "__main__":
    unittest.main()
