"""GET /v1/info, /v1/capabilities, /v1/subjects — the REST API's static metadata.
In-process through FastAPI's TestClient; every infrastructure entry point is
patched and must stay unused: metadata never calls the backend.
"""
import importlib.util
import json
import os
import unittest
from unittest.mock import patch

if importlib.util.find_spec("fastapi") is None:
    raise unittest.SkipTest("REST API tests need the optional dependency: pip install -r requirements-api.txt")
if importlib.util.find_spec("httpx2") is None and importlib.util.find_spec("httpx") is None:
    raise unittest.SkipTest("REST API tests need an HTTP client for TestClient: pip install httpx")

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402
import client  # noqa: E402
import config  # noqa: E402
import public_views  # noqa: E402
from models import CONFIG_NAMES, DEFAULT_CONFIG  # noqa: E402
from subjects import SUBJECTS  # noqa: E402

BASE_URL = "http://127.0.0.1:8001"
METADATA_PATHS = ("/v1/info", "/v1/capabilities", "/v1/subjects")
# Words that would mean MCP concepts or infrastructure leaked into a REST response.
FORBIDDEN_WORDS = ("mcp", "rag://", "tool", "resource", "stdio", "streamable", "transport", "aws", "bedrock",
                   "opensearch", "aoss", "nova-", "nova lite", "titan", "amazon", "arn:", "collection", "endpoint",
                   "index", "region", "contract_version", ".py", "/mcp")


class _MetadataTestCase(unittest.TestCase):
    role = "employee"

    def setUp(self):
        self.guards = [patch(target).start() for target in
                       ("client.opensearch_client", "manage.aoss_client", "manage.collection_health", "ask.ask")]
        self.addCleanup(patch.stopall)
        self.client = TestClient(api_server.build_app(self.role), base_url=BASE_URL, raise_server_exceptions=False)

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def get(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/json")
        return response.json()


class InfoTests(_MetadataTestCase):
    def test_exact_info_for_an_employee_server(self):
        self.assertEqual(self.get("/v1/info"), {"name": "novaops-knowledge-base", "version": "0.1.0",
                                                "api_version": "v1", "role": "employee"})

    def test_info_reports_the_same_identity_as_the_openapi_document(self):
        spec = self.get("/openapi.json")
        info = self.get("/v1/info")
        self.assertEqual((spec["info"]["title"], spec["info"]["version"]), (info["name"], info["version"]))


class ManagerInfoTests(_MetadataTestCase):
    role = "manager"

    def test_info_reports_the_servers_fixed_role(self):
        self.assertEqual(self.get("/v1/info")["role"], "manager")

    def test_capabilities_and_subjects_do_not_depend_on_the_role(self):
        employee = TestClient(api_server.build_app("employee"), base_url=BASE_URL)
        for path in ("/v1/capabilities", "/v1/subjects"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path), employee.get(path).json())


class CapabilitiesTests(_MetadataTestCase):
    def setUp(self):
        super().setUp()
        self.caps = self.get("/v1/capabilities")

    def test_exact_top_level_shape(self):
        self.assertEqual(set(self.caps), {"configurations", "default_configuration", "judging", "security", "limits"})

    def test_configurations_are_the_shared_public_descriptions_in_order(self):
        self.assertEqual(self.caps["configurations"],
                         [c.model_dump(mode="json") for c in public_views.configuration_capabilities()])
        self.assertEqual([c["name"] for c in self.caps["configurations"]], list(CONFIG_NAMES))
        for configuration in self.caps["configurations"]:
            self.assertEqual(set(configuration),
                             {"name", "subject_filter", "reranking", "context_selection", "summary"})

    def test_default_configuration(self):
        self.assertEqual(self.caps["default_configuration"], DEFAULT_CONFIG)

    def test_judging(self):
        judging = self.caps["judging"]
        self.assertEqual(set(judging), {"field", "default", "judges", "note"})
        self.assertEqual((judging["field"], judging["default"]), ("judge", False))
        self.assertEqual(judging["judges"], ["faithfulness", "context_relevance", "context_completeness", "refusal"])
        self.assertIn("withheld", judging["note"])

    @unittest.skipIf(importlib.util.find_spec("mcp") is None, "compares with the optional MCP server")
    def test_the_judges_are_the_ones_the_mcp_server_also_reports(self):
        import mcp_server
        self.assertEqual(self.caps["judging"]["judges"], mcp_server.build_capabilities("employee").judgement.judges)

    def test_security_describes_the_rest_behavior(self):
        security = self.caps["security"]
        self.assertEqual(set(security), {"role", "access_filter", "security_audit"})
        self.assertIn("fixed at startup", security["role"])
        self.assertIn("fail closed", security["access_filter"])
        self.assertIn("HTTP 200", security["security_audit"])
        self.assertIn("withheld", security["security_audit"])

    def test_limits_are_the_ones_the_request_schema_enforces(self):
        self.assertEqual(self.caps["limits"], {"question_max_chars": public_views.MAX_QUESTION_CHARS,
                                               "updated_on_or_after_format": "YYYY-MM-DD"})
        request = self.get("/openapi.json")["components"]["schemas"]["AskRequest"]
        self.assertEqual(request["properties"]["question"]["maxLength"], self.caps["limits"]["question_max_chars"])

    def test_no_tuning_values_are_exposed(self):
        def keys(value):
            if isinstance(value, dict):
                return set(value) | {k for v in value.values() for k in keys(v)}
            if isinstance(value, list):
                return {k for v in value for k in keys(v)}
            return set()
        for key in ("top_k", "pool_size", "candidate_pool_size", "static_top_k", "baseline_top_k",
                    "dynamic_threshold", "min_rerank_score"):
            self.assertNotIn(key, keys(self.caps))


class SubjectsTests(_MetadataTestCase):
    def test_exact_subject_list(self):
        self.assertEqual(self.get("/v1/subjects"), {"subjects": list(SUBJECTS)})


class MetadataSafetyTests(_MetadataTestCase):
    def test_no_mcp_concept_or_infrastructure_identifier_leaks(self):
        rendered = json.dumps([self.get(path) for path in METADATA_PATHS]).lower()
        for word in FORBIDDEN_WORDS:
            with self.subTest(word=word):
                self.assertNotIn(word, rendered)
        for value in (config.AWS_REGION, config.BEDROCK_MODEL_ID, config.BEDROCK_EMBEDDING_MODEL_ID,
                      config.OPENSEARCH_COLLECTION, client.INDEX_NAME):
            with self.subTest(value=value):
                self.assertNotIn(value.lower(), rendered)

    def test_metadata_is_get_only(self):
        for path in METADATA_PATHS:
            for method in ("POST", "PUT", "DELETE"):
                with self.subTest(path=path, method=method):
                    response = self.client.request(method, path, content=b"{}",
                                                   headers={"Content-Type": "application/json"})
                    self.assertEqual(response.status_code, 405)
                    self.assertEqual(response.headers["content-type"], "application/problem+json")
                    self.assertEqual(response.headers["allow"], "GET")

    def test_a_foreign_host_is_refused(self):
        for path in METADATA_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Host": "evil.example"})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["type"], "urn:novaops:problem:invalid-host")

    def test_unknown_metadata_routes_are_not_found_problems(self):
        for path in ("/v1/info/extra", "/v1/subject", "/v1/capabilities/baseline", "/v2/info", "/info"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["type"], "urn:novaops:problem:not-found")


class MetadataOpenApiTests(_MetadataTestCase):
    EXPECTED = {"/v1/info": "ApiInfo", "/v1/capabilities": "ApiCapabilities", "/v1/subjects": "SubjectList"}

    def setUp(self):
        super().setUp()
        self.spec = self.get("/openapi.json")

    def test_each_endpoint_is_a_documented_get_with_its_response_model(self):
        for path, model in self.EXPECTED.items():
            with self.subTest(path=path):
                self.assertEqual(set(self.spec["paths"][path]), {"get"})
                operation = self.spec["paths"][path]["get"]
                self.assertNotIn("requestBody", operation)
                self.assertNotIn("parameters", operation)
                self.assertNotIn("422", operation["responses"])
                ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
                self.assertEqual(ref.rsplit("/", 1)[1], model)

    def test_documented_fields_match_the_responses(self):
        schemas = self.spec["components"]["schemas"]
        for path, model in self.EXPECTED.items():
            with self.subTest(path=path):
                self.assertEqual(set(schemas[model]["properties"]), set(self.get(path)))

    def test_the_whole_api_surface(self):
        self.assertEqual(set(self.spec["paths"]),
                         {"/healthz", "/v1/ask", "/v1/health", "/v1/info", "/v1/capabilities", "/v1/subjects"})


if __name__ == "__main__":
    unittest.main()
