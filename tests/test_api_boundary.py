"""The REST dependency boundary: the REST API is an optional adapter, never a
dependency of the RAG application, and independent of the MCP adapter. Static
checks only — requirement files are read as text and modules are parsed with ast,
never imported — so these tests need neither FastAPI nor AWS.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIPPED_DIRS = {"tests", "__pycache__", "runs", "logs", "reference"}
API_ADAPTER = "api_server.py"
WEB_PACKAGES = ("fastapi", "starlette", "uvicorn")


def _requirement_names(path: Path) -> list[str]:
    lines = (line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [re.match(r"[A-Za-z0-9_.-]+", line).group(0).lower() for line in lines if line and not line.startswith("-")]


def _project_modules() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.py")
                  if not any(part.startswith(".") or part in SKIPPED_DIRS
                             for part in path.relative_to(ROOT).parts[:-1]))


def _imported_modules(source: str) -> list[str]:
    """Absolute module names a source imports, in order, at any nesting level."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return names


def _imports_package(source: str, package: str) -> bool:
    return any(name == package or name.startswith(package + ".") for name in _imported_modules(source))


def _offenders(package: str, allowed: frozenset[str] = frozenset()) -> list[str]:
    offenders = []
    for path in _project_modules():
        relative = path.relative_to(ROOT).as_posix()
        if relative not in allowed and _imports_package(path.read_text(encoding="utf-8"), package):
            offenders.append(relative)
    return offenders


class RequirementFilesTests(unittest.TestCase):
    def test_the_web_stack_is_not_a_dependency_of_the_application_or_of_mcp(self):
        for name in ("requirements.txt", "requirements-mcp.txt"):
            with self.subTest(file=name):
                names = _requirement_names(ROOT / name)
                for package in WEB_PACKAGES:
                    self.assertNotIn(package, names)

    def test_api_requirements_extend_the_main_requirements_with_fastapi_and_uvicorn(self):
        lines = [line.split("#", 1)[0].strip()
                 for line in (ROOT / "requirements-api.txt").read_text(encoding="utf-8").splitlines()]
        lines = [line for line in lines if line]
        self.assertEqual(lines[0], "-r requirements.txt")
        self.assertEqual(sorted(_requirement_names(ROOT / "requirements-api.txt")), ["fastapi", "uvicorn"])
        self.assertNotIn("mcp", _requirement_names(ROOT / "requirements-api.txt"))


class ImportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / API_ADAPTER).read_text(encoding="utf-8")

    def test_only_the_rest_adapter_imports_the_web_stack(self):
        for package in WEB_PACKAGES:
            with self.subTest(package=package):
                self.assertEqual(_offenders(package, allowed=frozenset({API_ADAPTER})), [])

    def test_nothing_imports_the_rest_adapter(self):
        self.assertEqual(_offenders("api_server"), [])

    def test_the_rest_adapter_is_independent_of_mcp_and_the_ui(self):
        for package in ("mcp", "mcp_server", "mcp_client", "streamlit", "ui", "runs"):
            with self.subTest(package=package):
                self.assertFalse(_imports_package(self.source, package))

    def test_the_rest_adapter_reaches_the_core_only_through_the_application_boundary(self):
        # Pipeline stages, judges and tooling stay behind ask.ask(); the adapter never assembles them itself.
        for module in ("eval", "planner", "reranker", "judges", "ingest", "create_index", "runs"):
            with self.subTest(module=module):
                self.assertFalse(_imports_package(self.source, module))
        self.assertTrue(_imports_package(self.source, "ask"))
        self.assertTrue(_imports_package(self.source, "manage"))  # collection_health(), the readiness use case
        self.assertTrue(_imports_package(self.source, "subjects"))  # the public subject vocabulary
        self.assertTrue(_imports_package(self.source, "public_views"))

    def test_config_is_the_first_project_import(self):
        first_party = [name for name in _imported_modules(self.source)
                       if (ROOT / f"{name.split('.')[0]}.py").exists()]
        self.assertEqual(first_party[0], "config")

    def test_the_detector_sees_the_forms_the_adapter_could_use(self):
        self.assertTrue(_imports_package("from fastapi import FastAPI", "fastapi"))
        self.assertTrue(_imports_package("def f():\n    import uvicorn\n", "uvicorn"))
        self.assertTrue(_imports_package("from starlette.requests import Request", "starlette"))
        self.assertFalse(_imports_package("import fastapix", "fastapi"))


if __name__ == "__main__":
    unittest.main()
