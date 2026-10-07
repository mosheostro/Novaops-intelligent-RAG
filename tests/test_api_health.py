"""GET /v1/health — readiness through the REST adapter: manage.collection_health()
projected by public_views.project_health(). In-process through FastAPI's
TestClient; the control-plane client, the data-plane client and the use cases are
patched, so no network and no AWS.
"""
import importlib.util
import os
import unittest
from unittest.mock import MagicMock, patch

if importlib.util.find_spec("fastapi") is None:
    raise unittest.SkipTest("REST API tests need the optional dependency: pip install -r requirements-api.txt")
if importlib.util.find_spec("httpx2") is None and importlib.util.find_spec("httpx") is None:
    raise unittest.SkipTest("REST API tests need an HTTP client for TestClient: pip install httpx")

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from botocore.exceptions import (  # noqa: E402
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    ReadTimeoutError,
)
from fastapi.testclient import TestClient  # noqa: E402

import api_server  # noqa: E402
import public_views  # noqa: E402
from manage import CollectionHealth  # noqa: E402

BASE_URL = "http://127.0.0.1:8001"
ENDPOINT = "https://SENTINEL-ENDPOINT.us-east-1.aoss.amazonaws.com"
SECRET = "SENTINEL-SECRET arn:aws:aoss:us-east-1:123456789012:collection/abc"
LEAKS = ("SENTINEL", "arn:aws", "123456789012", "us-east-1", "amazonaws", "AccessDenied")
HEALTH_KEYS = {"ready", "collection_state", "index_present", "chunk_count", "data_plane_reachable"}

READY = CollectionHealth(status="ACTIVE", endpoint=ENDPOINT, index_exists=True, chunk_count=400,
                         data_plane_error=None)
NOT_READY = {
    "empty_index": CollectionHealth(status="ACTIVE", endpoint=ENDPOINT, index_exists=True, chunk_count=0,
                                    data_plane_error=None),
    "no_index": CollectionHealth(status="ACTIVE", endpoint=ENDPOINT, index_exists=False, chunk_count=None,
                                 data_plane_error=None),
    "data_plane_unreachable": CollectionHealth(status="ACTIVE", endpoint=ENDPOINT, index_exists=None,
                                               chunk_count=None, data_plane_error=f"cannot reach {SECRET}"),
    "creating": CollectionHealth(status="CREATING", endpoint=ENDPOINT, index_exists=None, chunk_count=None,
                                 data_plane_error=None),
    "missing": CollectionHealth(status=None, endpoint=None, index_exists=None, chunk_count=None,
                                data_plane_error=None),
}


class _HealthTestCase(unittest.TestCase):
    def setUp(self):
        self.opensearch_client = patch("client.opensearch_client").start()
        self.aoss_client = patch("manage.aoss_client").start()
        self.collection_health = patch("manage.collection_health", return_value=READY).start()
        self.ask = patch("ask.ask").start()
        self.addCleanup(patch.stopall)
        self.client = TestClient(api_server.build_app("employee"), base_url=BASE_URL, raise_server_exceptions=False)

    def assertNoLeak(self, response):
        for leak in LEAKS:
            self.assertNotIn(leak, response.text)


class ReadinessTests(_HealthTestCase):
    def test_ready_is_200_with_the_shared_public_projection(self):
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.json(), public_views.project_health(READY).model_dump(mode="json"))
        self.assertEqual(response.json(), {"ready": True, "collection_state": "ACTIVE", "index_present": True,
                                           "chunk_count": 400, "data_plane_reachable": True})
        self.assertNoLeak(response)

    def test_the_existing_health_use_case_is_called_with_the_control_plane_client(self):
        self.client.get("/v1/health")
        self.aoss_client.assert_called_once_with()
        self.collection_health.assert_called_once_with(self.aoss_client.return_value)
        self.ask.assert_not_called()

    def test_the_adapter_uses_the_shared_projection_itself(self):
        self.assertIs(api_server.project_health, public_views.project_health)
        self.assertIs(api_server.HealthResult, public_views.HealthResult)

    def test_not_ready_is_503_with_the_same_safe_health_body(self):
        for name, health in NOT_READY.items():
            with self.subTest(state=name):
                self.collection_health.return_value = health
                response = self.client.get("/v1/health")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers["content-type"], "application/json")  # a result, not a problem
                body = response.json()
                self.assertEqual(set(body), HEALTH_KEYS)
                self.assertIs(body["ready"], False)
                self.assertEqual(body, public_views.project_health(health).model_dump(mode="json"))
                self.assertNoLeak(response)

    def test_readiness_is_decided_by_the_shared_projection_alone(self):
        with patch("api_server.project_health", wraps=public_views.project_health) as projection:
            self.client.get("/v1/health")
        projection.assert_called_once_with(READY)


class HealthFailureTests(_HealthTestCase):
    FAILURES = {
        "access_denied": (ClientError({"Error": {"Code": "AccessDenied", "Message": SECRET}}, "BatchGetCollection"),
                          503, "service-unavailable"),
        "no_credentials": (NoCredentialsError(), 503, "service-unavailable"),
        "unreachable": (EndpointConnectionError(endpoint_url=ENDPOINT), 503, "service-unavailable"),
        "system_exit": (SystemExit(SECRET), 503, "service-unavailable"),
        "timeout": (ReadTimeoutError(endpoint_url=ENDPOINT), 504, "service-timeout"),
        "unexpected": (RuntimeError(SECRET), 500, "internal-error"),
    }

    def test_a_backend_failure_is_a_fixed_problem_without_details(self):
        for name, (error, status, problem) in self.FAILURES.items():
            with self.subTest(failure=name):
                self.collection_health.side_effect = error
                response = self.client.get("/v1/health")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers["content-type"], "application/problem+json")
                self.assertEqual(response.json()["type"], f"urn:novaops:problem:{problem}")
                self.assertEqual(set(response.json()), {"type", "title", "status", "detail"})
                self.assertNoLeak(response)

    def test_a_failure_creating_the_control_plane_client_is_a_503_problem(self):
        self.aoss_client.side_effect = NoCredentialsError()
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["type"], "urn:novaops:problem:service-unavailable")
        self.collection_health.assert_not_called()

    def test_the_server_stays_usable_after_a_health_failure(self):
        self.collection_health.side_effect = [SystemExit(SECRET), READY]
        self.assertEqual(self.client.get("/v1/health").status_code, 503)
        self.assertEqual(self.client.get("/v1/health").status_code, 200)
        self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_failures_are_logged_by_category_and_type_only(self):
        self.collection_health.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": SECRET}}, "BatchGetCollection")
        with self.assertLogs("api_server", level="WARNING") as logs:
            self.client.get("/v1/health")
        rendered = "\n".join(logs.output)
        self.assertIn("service_unavailable", rendered)
        for leak in LEAKS:
            self.assertNotIn(leak, rendered)


class RealHealthUseCaseTests(unittest.TestCase):
    """The real manage.collection_health() behind the endpoint, with only its two
    clients faked — proves REST adds no readiness logic of its own."""

    def setUp(self):
        self.aoss = MagicMock()
        self.aoss.batch_get_collection.return_value = {"collectionDetails": [
            {"status": "ACTIVE", "collectionEndpoint": ENDPOINT, "id": "SENTINEL-ID"}]}
        patch("manage.aoss_client", return_value=self.aoss).start()
        self.data_plane = patch("client.opensearch_client").start()
        self.data_plane.return_value.indices.exists.return_value = True
        self.data_plane.return_value.count.return_value = {"count": 400}
        self.addCleanup(patch.stopall)
        self.client = TestClient(api_server.build_app("employee"), base_url=BASE_URL, raise_server_exceptions=False)

    def test_an_active_populated_collection_is_ready(self):
        response = self.client.get("/v1/health")
        self.assertEqual((response.status_code, response.json()["ready"], response.json()["chunk_count"]),
                         (200, True, 400))
        self.assertNotIn("SENTINEL", response.text)

    def test_an_unreachable_data_plane_is_a_not_ready_result_not_an_error(self):
        self.data_plane.side_effect = SystemExit(SECRET)  # client.resolve_endpoint exits; collection_health records it
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.json(), {"ready": False, "collection_state": "ACTIVE", "index_present": None,
                                           "chunk_count": None, "data_plane_reachable": False})
        self.assertNotIn("SENTINEL", response.text)


class HealthBoundaryTests(_HealthTestCase):
    def tearDown(self):
        self.collection_health.assert_not_called()
        self.aoss_client.assert_not_called()

    def test_health_is_get_only(self):
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                response = self.client.request(method.upper(), "/v1/health", content=b"{}",
                                               headers={"Content-Type": "application/json"})
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["content-type"], "application/problem+json")
                self.assertEqual(response.headers["allow"], "GET")

    def test_a_foreign_host_is_refused_before_any_backend_call(self):
        response = self.client.get("/v1/health", headers={"Host": "evil.example"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["type"], "urn:novaops:problem:invalid-host")

    def test_liveness_still_makes_no_backend_call(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        self.opensearch_client.assert_not_called()
        self.ask.assert_not_called()


class HealthOpenApiTests(_HealthTestCase):
    def setUp(self):
        super().setUp()
        self.spec = self.client.get("/openapi.json").json()
        self.operation = self.spec["paths"]["/v1/health"]["get"]

    @staticmethod
    def _name(content):
        return content["schema"]["$ref"].rsplit("/", 1)[1]

    def test_health_is_documented_as_get_only_without_a_request_body(self):
        self.assertEqual(set(self.spec["paths"]["/v1/health"]), {"get"})
        self.assertNotIn("requestBody", self.operation)
        self.assertNotIn("parameters", self.operation)

    def test_ready_and_not_ready_return_the_health_result_and_failures_are_problems(self):
        responses = self.operation["responses"]
        self.assertEqual(self._name(responses["200"]["content"]["application/json"]), "HealthResult")
        not_ready = responses["503"]["content"]
        self.assertEqual(self._name(not_ready["application/json"]), "HealthResult")
        self.assertEqual(self._name(not_ready["application/problem+json"]), "Problem")
        for status in ("500", "504"):
            with self.subTest(status=status):
                self.assertEqual(list(responses[status]["content"]), ["application/problem+json"])
        self.assertNotIn("422", responses)
        self.assertEqual(set(self.spec["components"]["schemas"]["HealthResult"]["properties"]), HEALTH_KEYS)


if __name__ == "__main__":
    unittest.main()
