"""api_server.py — the REST adapter's skeleton: startup checks, the HTTP boundary
(Host allow-list, JSON-only bodies, no CORS), the problem+json error contract and
liveness. Driven in-process through FastAPI's TestClient: no subprocess, no
network, no AWS — infrastructure entry points are patched and must stay unused.

Needs the optional REST dependencies (requirements-api.txt). Without them the
module is skipped; the dependency-boundary tests in test_api_boundary.py still run.
"""
import importlib.util
import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

if importlib.util.find_spec("fastapi") is None:
    raise unittest.SkipTest("REST API tests need the optional dependency: pip install -r requirements-api.txt")
if importlib.util.find_spec("httpx2") is None and importlib.util.find_spec("httpx") is None:
    raise unittest.SkipTest("REST API tests need an HTTP client for TestClient: pip install httpx")

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from botocore.exceptions import ClientError, ReadTimeoutError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from opensearchpy.exceptions import ConnectionTimeout, OpenSearchException  # noqa: E402
from pydantic import BaseModel, ConfigDict  # noqa: E402

import api_server  # noqa: E402
from retrieval import SUPPORTED_AUDIENCES, UnsupportedAudienceError  # noqa: E402

INVALID_ROLES = ("user", "boss", "", "Employee", " employee")
BASE_URL = "http://127.0.0.1:8001"
PROBLEM_KEYS = {"type", "title", "status", "detail"}
SECRET = "SENTINEL-SECRET arn:aws:aoss:us-east-1:123456789012:collection/abc"


class _InfrastructureGuard(unittest.TestCase):
    """Every infrastructure entry point is patched; tests assert they stay unused."""

    def setUp(self):
        self.opensearch_client = patch("client.opensearch_client").start()
        self.aoss_client = patch("manage.aoss_client").start()
        self.ask = patch("ask.ask").start()
        self.addCleanup(patch.stopall)
        self.app = api_server.build_app("employee")
        self.client = TestClient(self.app, base_url=BASE_URL, raise_server_exceptions=False)

    def assertNoInfrastructureCall(self):
        for mock in (self.opensearch_client, self.aoss_client, self.ask):
            mock.assert_not_called()

    def assertProblem(self, response, status: int, problem: str):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.headers["content-type"], "application/problem+json")
        body = response.json()
        self.assertTrue(PROBLEM_KEYS <= set(body), body)
        self.assertEqual(body["status"], status)
        self.assertEqual(body["type"], f"urn:novaops:problem:{problem}")
        self.assertTrue(body["title"] and body["detail"])
        return body


class BuildAppTests(_InfrastructureGuard):
    def test_every_supported_role_builds_an_app(self):
        for role in sorted(SUPPORTED_AUDIENCES):
            with self.subTest(role=role):
                self.assertIsNotNone(api_server.build_app(role))

    def test_an_unsupported_role_never_builds_an_app(self):
        with patch("api_server.FastAPI") as fastapi_class:
            for role in INVALID_ROLES:
                with self.subTest(role=role), self.assertRaises(UnsupportedAudienceError):
                    api_server.build_app(role)
            fastapi_class.assert_not_called()

    def test_identity_is_the_public_name_and_the_api_servers_own_version(self):
        self.assertEqual(self.app.title, "novaops-knowledge-base")
        self.assertEqual(self.app.version, "0.1.0")
        self.assertEqual(api_server.API_SERVER_VERSION, "0.1.0")

    @unittest.skipIf(importlib.util.find_spec("mcp") is None, "compares with the optional MCP server")
    def test_the_public_name_is_the_one_the_mcp_server_announces(self):
        import mcp_server
        self.assertEqual(api_server.SERVICE_NAME, mcp_server.SERVER_NAME)

    def test_building_an_app_touches_no_infrastructure(self):
        self.assertNoInfrastructureCall()


class StartupTests(_InfrastructureGuard):
    def _main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with patch("api_server.uvicorn.run") as run, redirect_stdout(out), redirect_stderr(err):
            try:
                api_server.main(list(argv))
                code = None
            except SystemExit as exit_:
                code = exit_.code
        return code, run, out.getvalue(), err.getvalue()

    def test_role_is_required(self):
        code, run, _, err = self._main()
        self.assertEqual(code, 2)
        self.assertIn("--role", err)
        run.assert_not_called()

    def test_an_unsupported_role_is_refused_on_stderr_before_serving(self):
        for role in INVALID_ROLES:
            with self.subTest(role=role):
                code, run, out, err = self._main("--role", role)
                self.assertEqual(code, 2)
                self.assertIn("unsupported role", err)
                self.assertEqual(out, "")
                run.assert_not_called()

    def test_a_non_loopback_host_is_refused_before_serving(self):
        for host in ("0.0.0.0", "::", "192.168.1.10", "example.com", "127.0.0.2", "LOCALHOST"):
            with self.subTest(host=host):
                code, run, _, err = self._main("--role", "employee", "--host", host)
                self.assertEqual(code, 2)
                self.assertIn("loopback", err)
                run.assert_not_called()

    def test_defaults_serve_one_process_on_ipv4_loopback_port_8001(self):
        code, run, _, _ = self._main("--role", "employee")
        self.assertIsNone(code)
        run.assert_called_once()
        app = run.call_args.args[0]
        self.assertEqual(app.title, "novaops-knowledge-base")
        self.assertEqual((run.call_args.kwargs["host"], run.call_args.kwargs["port"]), ("127.0.0.1", 8001))
        self.assertNotIn("workers", run.call_args.kwargs)  # an app object: always a single process

    def test_every_loopback_host_and_a_custom_port_are_accepted(self):
        for host in ("127.0.0.1", "localhost", "::1"):
            with self.subTest(host=host):
                code, run, _, _ = self._main("--role", "manager", "--host", host, "--port", "9001")
                self.assertIsNone(code)
                self.assertEqual((run.call_args.kwargs["host"], run.call_args.kwargs["port"]), (host, 9001))
        self.assertNoInfrastructureCall()


class LivenessTests(_InfrastructureGuard):
    def test_healthz_reports_the_process_alive_without_any_backend_call(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertNoInfrastructureCall()


class HostHeaderTests(_InfrastructureGuard):
    def test_loopback_host_headers_are_accepted_with_or_without_a_port(self):
        for host in ("127.0.0.1", "127.0.0.1:8001", "localhost", "localhost:8001", "LocalHost:8001",
                     "[::1]", "[::1]:8001"):
            with self.subTest(host=host):
                self.assertEqual(self.client.get("/healthz", headers={"Host": host}).status_code, 200)

    def test_a_foreign_host_header_is_rejected_as_a_problem(self):
        for host in ("evil.example", "evil.example:8001", "127.0.0.1.evil.example", "localhost.evil.example",
                     "0.0.0.0:8001", "192.168.1.10", "[::2]:8001", "::1", ""):
            with self.subTest(host=host):
                body = self.assertProblem(self.client.get("/healthz", headers={"Host": host}), 400,
                                          "invalid-host")
                if host:
                    self.assertNotIn(host, str(body))  # the header is not echoed
        self.assertNoInfrastructureCall()


class ContentTypeTests(_InfrastructureGuard):
    def test_a_body_request_without_a_json_content_type_is_refused(self):
        for headers in ({}, {"Content-Type": "text/plain"}, {"Content-Type": "text/plain;charset=UTF-8"},
                        {"Content-Type": "application/x-www-form-urlencoded"},
                        {"Content-Type": "multipart/form-data; boundary=x"}, {"Content-Type": "application/jsonx"}):
            with self.subTest(headers=headers):
                self.assertProblem(self.client.post("/healthz", content=b'{"a": 1}', headers=headers), 415,
                                   "unsupported-media-type")

    def test_a_json_content_type_passes_the_gate(self):
        for content_type in ("application/json", "application/json; charset=utf-8", "Application/JSON"):
            with self.subTest(content_type=content_type):
                response = self.client.post("/healthz", content=b"{}", headers={"Content-Type": content_type})
                self.assertProblem(response, 405, "method-not-allowed")  # past the gate, then the router

    def test_requests_without_a_body_method_need_no_content_type(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)


class NoCorsTests(_InfrastructureGuard):
    def test_no_cross_origin_access_is_granted(self):
        preflight = self.client.options("/healthz", headers={
            "Origin": "https://evil.example", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"})
        self.assertNotEqual(preflight.status_code, 200)
        simple = self.client.get("/healthz", headers={"Origin": "https://evil.example"})
        for response in (preflight, simple):
            self.assertFalse([h for h in response.headers if h.lower().startswith("access-control-")])


class RoutingProblemTests(_InfrastructureGuard):
    def test_an_unknown_route_is_a_not_found_problem(self):
        body = self.assertProblem(self.client.get("/v1/nope-SENTINEL"), 404, "not-found")
        self.assertNotIn("SENTINEL", str(body))

    def test_an_unsupported_method_is_a_problem_that_keeps_the_allow_header(self):
        response = self.client.delete("/healthz")
        self.assertProblem(response, 405, "method-not-allowed")
        self.assertEqual(response.headers["allow"], "GET")


class _Echo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str


class ErrorContractTests(_InfrastructureGuard):
    """The centralized error handling, exercised through routes added only for the test."""

    def setUp(self):
        super().setUp()

        def echo(body: _Echo) -> dict:
            return {"ok": True}

        def boom() -> dict:
            raise RuntimeError(SECRET)

        def failing(kind: str) -> dict:
            errors = {
                "exit": SystemExit(SECRET),
                "opensearch": OpenSearchException(SECRET),
                "client": ClientError({"Error": {"Code": "AccessDenied", "Message": SECRET}}, "Converse"),
                "timeout": ConnectionTimeout("TIMEOUT", SECRET, Exception(SECRET)),
                "read_timeout": ReadTimeoutError(endpoint_url=SECRET),
                "role": UnsupportedAudienceError(SECRET),
                "internal": KeyError(SECRET),
            }

            def use_case():
                raise errors[kind]
            return api_server.run_use_case("test", use_case)

        def http_error() -> dict:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=SECRET)

        self.app.add_api_route("/_test/http-error", http_error, methods=["GET"])
        self.app.add_api_route("/_test/echo", echo, methods=["POST"])
        self.app.add_api_route("/_test/boom", boom, methods=["GET"])
        self.app.add_api_route("/_test/fail/{kind}", failing, methods=["GET"])

    def test_validation_errors_are_problems_listing_fields_without_echoing_input(self):
        for payload in (b'{"question": 7, "extra": "SENTINEL-INPUT"}', b'{"question": ["SENTINEL-INPUT"]}',
                        b'{"question": "q", "role": "SENTINEL-INPUT"}', b'{not json SENTINEL-INPUT'):
            with self.subTest(payload=payload):
                response = self.client.post("/_test/echo", content=payload,
                                            headers={"Content-Type": "application/json"})
                body = self.assertProblem(response, 422, "validation-error")
                self.assertTrue(body["errors"])
                for error in body["errors"]:
                    self.assertEqual(set(error), {"location", "message", "type"})
                self.assertNotIn("SENTINEL-INPUT", response.text)

    def test_any_other_http_error_keeps_its_status_but_not_its_detail(self):
        response = self.client.get("/_test/http-error")
        self.assertProblem(response, 400, "http-error")
        self.assertEqual(response.json()["title"], "Bad Request")
        self.assertNotIn("SENTINEL", response.text)

    def test_an_unknown_field_is_located_by_its_name_but_its_value_is_not_echoed(self):
        response = self.client.post("/_test/echo", content=b'{"question": "q", "role": "SENTINEL-VALUE"}',
                                    headers={"Content-Type": "application/json"})
        body = self.assertProblem(response, 422, "validation-error")
        self.assertEqual([(e["location"], e["type"]) for e in body["errors"]],
                         [(["body", "role"], "extra_forbidden")])
        self.assertNotIn("SENTINEL-VALUE", response.text)

    def test_an_unexpected_exception_is_a_generic_internal_problem(self):
        response = self.client.get("/_test/boom")
        self.assertProblem(response, 500, "internal-error")
        self.assertNotIn("SENTINEL", response.text)

    def test_each_failure_category_maps_to_its_fixed_problem(self):
        expected = {"exit": (503, "service-unavailable"), "opensearch": (503, "service-unavailable"),
                    "client": (503, "service-unavailable"), "timeout": (504, "service-timeout"),
                    "read_timeout": (504, "service-timeout"), "role": (500, "server-misconfigured"),
                    "internal": (500, "internal-error")}
        for kind, (status, problem) in expected.items():
            with self.subTest(kind=kind):
                response = self.client.get(f"/_test/fail/{kind}")
                self.assertProblem(response, status, problem)
                for leak in ("SENTINEL", "arn:aws", "123456789012", "us-east-1", "AccessDenied"):
                    self.assertNotIn(leak, response.text)

    def test_a_backend_system_exit_fails_one_request_and_the_server_keeps_serving(self):
        self.assertEqual(self.client.get("/_test/fail/exit").status_code, 503)
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/_test/fail/exit").status_code, 503)

    def test_run_use_case_returns_the_result_when_nothing_fails(self):
        self.assertEqual(api_server.run_use_case("test", lambda: 42), 42)

    def test_known_failures_are_logged_by_category_and_type_only(self):
        with self.assertLogs("api_server", level="WARNING") as logs:
            self.client.get("/_test/fail/exit")
        self.assertIn("service_unavailable", logs.output[0])
        self.assertIn("SystemExit", logs.output[0])
        self.assertNotIn("SENTINEL", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
