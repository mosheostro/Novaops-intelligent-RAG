"""The README's REST endpoint table stays aligned with the REST API's real OpenAPI
contract: every documented endpoint exists with that method, and every endpoint
the API serves is documented. /docs and /openapi.json stay the authoritative
contract; this only stops the README from drifting away from it. No AWS: the
OpenAPI document is generated in-process without calling the backend.
"""
import importlib.util
import os
import re
import unittest
from pathlib import Path

if importlib.util.find_spec("fastapi") is None:
    raise unittest.SkipTest("REST API tests need the optional dependency: pip install -r requirements-api.txt")

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import api_server  # noqa: E402

README = Path(__file__).resolve().parent.parent / "README.md"
ENDPOINT_ROW = re.compile(r"^\|\s*`(GET|POST|PUT|PATCH|DELETE) (/[^`\s]*)`\s*\|", re.MULTILINE)


def _rest_section(markdown: str) -> str:
    start = markdown.index("\n## REST API\n")
    end = markdown.find("\n## ", start + 1)
    return markdown[start:end if end != -1 else None]


class ReadmeMatchesOpenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = api_server.build_app("employee").openapi()
        cls.served = {(method.upper(), path) for path, operations in spec["paths"].items() for method in operations}
        cls.section = _rest_section(README.read_text(encoding="utf-8"))
        cls.documented = set(ENDPOINT_ROW.findall(cls.section))

    def test_the_readme_documents_endpoints_at_all(self):
        self.assertGreaterEqual(len(self.documented), 1)  # the table was found and parsed

    def test_every_documented_endpoint_is_served_with_that_method(self):
        self.assertEqual(self.documented - self.served, set())

    def test_every_served_endpoint_is_documented(self):
        self.assertEqual(self.served - self.documented, set())

    def test_the_readme_points_to_the_authoritative_contract(self):
        for text in ("/docs", "/openapi.json"):
            self.assertIn(text, self.section)


if __name__ == "__main__":
    unittest.main()
