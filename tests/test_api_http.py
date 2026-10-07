"""The REST API as a real process: `python api_server.py` under uvicorn on a free
loopback port, reached over plain HTTP (urllib) — the same path a curl user takes:
HTTP -> FastAPI route -> ask.ask() / manage.collection_health() -> boto3/OpenSearch.

Two layers:

* LoopbackProcessTests (always run): placeholder configuration, and every AWS call
  is sent by botocore's standard AWS_ENDPOINT_URL setting to a closed loopback port
  with AWS_MAX_ATTEMPTS=1. The real use cases run and fail fast on loopback — no AWS
  contact, no DNS — which exercises the real failure mapping end to end.

* LiveBackendTests (opt-in): the real backend from .env — Bedrock and the live
  OpenSearch collection. Skipped unless NOVAOPS_LIVE_TESTS=1, because every ask
  costs model calls. Read-only: nothing is written to the index.

        $env:NOVAOPS_LIVE_TESTS = "1"; .venv\\Scripts\\python.exe -m unittest tests.test_api_http -v

Skipped without the optional REST dependency (requirements-api.txt).
"""
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

if importlib.util.find_spec("fastapi") is None:
    raise unittest.SkipTest("REST API tests need the optional dependency: pip install -r requirements-api.txt")

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
                "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION")
PLACEHOLDER = "test-value"  # a valid-format region too: boto3 validates the region at import
READY_TIMEOUT = 30
LIVE = os.environ.get("NOVAOPS_LIVE_TESTS") == "1"
PUBLIC_ASK_KEYS = {"answer", "config", "role", "status", "planned_subjects", "cutoff", "retrieval", "sources",
                   "security_audit", "judgement"}
INTERNAL_KEYS = {"text", "context_texts", "vector_score", "vector_rank", "top_k_requested", "audience",
                 "violating_sources", "candidates", "question", "subjects_applied", "endpoint", "data_plane_error"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


class _ApiServer:
    """One real `api_server.py` process; stdout and stderr go to a temporary file
    so tests can inspect what it logged."""

    def __init__(self, role: str, env: dict[str, str]):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.log = tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace")
        self.process = subprocess.Popen(
            [sys.executable, "api_server.py", "--role", role, "--port", str(self.port)],
            cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8", **env},
            stdout=self.log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + READY_TIMEOUT
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"REST server exited during startup:\n{self.output()}")
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.2).close()
                return
            except OSError:
                if time.monotonic() > deadline:
                    self.stop()
                    raise RuntimeError("REST server did not start listening in time")
                time.sleep(0.1)

    def request(self, method: str, path: str, body=None, timeout: float = 30,
                **headers) -> tuple[int, dict, str]:
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        headers = {name.replace("_", "-"): value for name, value in headers.items()}  # Content_Type=...
        if data is not None:
            headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read().decode()
        except urllib.error.HTTPError as error:
            with error:
                return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read().decode()

    def get(self, path: str, **headers):
        return self.request("GET", path, **headers)

    def post(self, path: str, body, timeout: float = 30, **headers):
        return self.request("POST", path, body, timeout=timeout, **headers)

    def output(self) -> str:
        self.log.seek(0)
        return self.log.read()

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.log.close()


class _ProblemAssertions(unittest.TestCase):
    def assertProblem(self, response, status: int, problem: str) -> dict:
        code, headers, text = response
        self.assertEqual(code, status, text)
        self.assertEqual(headers["content-type"], "application/problem+json")
        body = json.loads(text)
        self.assertEqual(body["type"], f"urn:novaops:problem:{problem}")
        self.assertEqual(body["status"], status)
        return body


class LoopbackProcessTests(_ProblemAssertions):
    """Real processes and real use cases; AWS replaced by a closed loopback port."""

    @classmethod
    def setUpClass(cls):
        dead_port = _free_port()  # nothing listens here: every AWS call is refused at once
        env = {**{name: PLACEHOLDER for name in REQUIRED_ENV},
               "AWS_ENDPOINT_URL": f"http://127.0.0.1:{dead_port}", "AWS_MAX_ATTEMPTS": "1",
               "AWS_RETRY_MODE": "standard"}
        env.pop("OPENSEARCH_ENDPOINT", None)
        cls.employee = _ApiServer("employee", env)
        cls.addClassCleanup(cls.employee.stop)
        cls.manager = _ApiServer("manager", env)
        cls.addClassCleanup(cls.manager.stop)

    def test_liveness_and_identity_per_process(self):
        code, _, text = self.employee.get("/healthz")
        self.assertEqual((code, json.loads(text)), (200, {"status": "ok"}))
        for server, role in ((self.employee, "employee"), (self.manager, "manager")):
            with self.subTest(role=role):
                code, _, text = server.get("/v1/info")
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(text), {"name": "novaops-knowledge-base", "version": "0.1.0",
                                                    "api_version": "v1", "role": role})

    def test_metadata_and_openapi_are_served(self):
        for path in ("/v1/capabilities", "/v1/subjects", "/openapi.json", "/docs"):
            with self.subTest(path=path):
                self.assertEqual(self.employee.get(path)[0], 200)

    def test_invalid_requests_are_422_problems_before_any_backend_call(self):
        for body, location in (({"question": "q", "role": "manager"}, ["body", "role"]),
                               ({"question": "q", "config": "bogus"}, ["body", "config"]),
                               ({"question": "q", "updated_on_or_after": "31/01/2025"},
                                ["body", "updated_on_or_after"]),
                               ({"question": "   "}, ["body", "question"])):
            with self.subTest(body=body):
                problem = self.assertProblem(self.employee.post("/v1/ask", body), 422, "validation-error")
                self.assertIn(location, [e["location"] for e in problem["errors"]])

    def test_the_http_boundary_holds_in_the_real_server(self):
        self.assertProblem(self.employee.post("/v1/ask", {"question": "q"}, Content_Type="text/plain"), 415,
                           "unsupported-media-type")
        self.assertProblem(self.employee.get("/healthz", Host="evil.example"), 400, "invalid-host")
        self.assertProblem(self.employee.get("/v1/nope"), 404, "not-found")
        response = self.employee.get("/v1/ask")
        self.assertProblem(response, 405, "method-not-allowed")
        self.assertEqual(response[1]["allow"], "POST")
        self.assertNotIn("access-control-allow-origin", self.employee.get("/healthz", Origin="https://x.example")[1])

    def test_an_unreachable_backend_is_a_503_problem_from_the_real_use_cases(self):
        self.assertProblem(self.employee.get("/v1/health"), 503, "service-unavailable")
        problem = self.assertProblem(self.employee.post("/v1/ask", {"question": "SENTINEL-QUESTION"}), 503,
                                     "service-unavailable")
        self.assertEqual(set(problem), {"type", "title", "status", "detail"})
        self.assertEqual(self.employee.get("/healthz")[0], 200)  # the process keeps serving
        log = self.employee.output()
        self.assertIn("ask failed: service_unavailable (EndpointConnectionError)", log)
        self.assertIn("health failed: service_unavailable (EndpointConnectionError)", log)
        self.assertNotIn("SENTINEL-QUESTION", log)  # the question never reaches the server log
        self.assertNotIn("Traceback", log)

    def test_an_invalid_startup_role_or_host_never_serves(self):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", **{name: PLACEHOLDER for name in REQUIRED_ENV}}
        for args, message in ((["--role", "boss"], "unsupported role"),
                              (["--role", "employee", "--host", "0.0.0.0"], "loopback")):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "api_server.py", *args], cwd=ROOT, env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)


@unittest.skipUnless(LIVE, "live REST tests call the real backend (Bedrock + OpenSearch); "
                           "set NOVAOPS_LIVE_TESTS=1 to run them")
class LiveBackendTests(_ProblemAssertions):
    """The real backend from .env. Questions are from the committed evaluation set.
    Role comparisons use the baseline configuration — plain k-NN, no planner or
    reranker — so which corpora come back is deterministic."""

    EMPLOYEE_QUESTION = "Does the company match my 401k contributions?"
    MANAGER_ONLY_QUESTION = "What steps do I need to take before terminating a report for underperformance?"
    ASK_TIMEOUT = 180

    @classmethod
    def setUpClass(cls):
        import config  # the real settings, loaded from .env; used only for leak checks
        cls.infrastructure = [value for value in (config.AWS_REGION, config.BEDROCK_MODEL_ID,
                                                  config.BEDROCK_EMBEDDING_MODEL_ID, config.OPENSEARCH_COLLECTION,
                                                  config.OPENSEARCH_ENDPOINT) if value]
        cls.infrastructure += ["amazonaws.com", "arn:aws", "novaops-kb", os.environ.get("AWS_ACCESS_KEY_ID", "")]
        cls.infrastructure = [value for value in cls.infrastructure if value]
        cls.employee = _ApiServer("employee", {})
        cls.addClassCleanup(cls.employee.stop)
        cls.manager = _ApiServer("manager", {})
        cls.addClassCleanup(cls.manager.stop)

    def assertNoLeak(self, text: str):
        for value in self.infrastructure:
            self.assertNotIn(value, text)

    def ask(self, server, body) -> dict:
        code, headers, text = server.post("/v1/ask", body, timeout=self.ASK_TIMEOUT)
        self.assertEqual(code, 200, text)
        self.assertEqual(headers["content-type"], "application/json")
        self.assertNoLeak(text)
        result = json.loads(text)
        self.assertEqual(set(result), PUBLIC_ASK_KEYS)  # the public projection, never a raw AskResult
        self.assertFalse(INTERNAL_KEYS & _keys(result))
        return result

    def test_health_is_ready_with_the_safe_projection(self):
        code, _, text = self.employee.request("GET", "/v1/health", timeout=120)
        self.assertEqual(code, 200, text)
        self.assertNoLeak(text)
        health = json.loads(text)
        self.assertEqual(set(health), {"ready", "collection_state", "index_present", "chunk_count",
                                       "data_plane_reachable"})
        self.assertEqual((health["ready"], health["collection_state"], health["index_present"]),
                         (True, "ACTIVE", True))
        self.assertGreater(health["chunk_count"], 0)

    def test_default_configuration_answers_from_the_handbook(self):
        result = self.ask(self.employee, {"question": self.EMPLOYEE_QUESTION})
        self.assertEqual((result["config"], result["role"], result["status"]),
                         ("filter + rerank dynamic", "employee", "selected"))
        self.assertTrue(result["answer"].strip())
        self.assertIsNone(result["judgement"])
        self.assertIsNotNone(result["planned_subjects"])
        self.assertTrue(result["sources"])
        self.assertEqual([s["rank"] for s in result["sources"]], list(range(1, len(result["sources"]) + 1)))
        self.assertEqual({s["corpus"] for s in result["sources"]}, {"handbook"})
        self.assertFalse(result["security_audit"]["violation"])

    def test_explicit_configuration_judge_false_and_a_past_cutoff(self):
        result = self.ask(self.employee, {"question": self.EMPLOYEE_QUESTION, "config": "baseline",
                                          "judge": False, "updated_on_or_after": "2000-01-01"})
        self.assertEqual((result["config"], result["status"], result["cutoff"]), ("baseline", "selected", "2000-01-01"))
        self.assertIsNone(result["planned_subjects"])  # baseline never runs the planner
        self.assertIsNone(result["judgement"])
        self.assertTrue(result["sources"])

    def test_a_future_cutoff_is_a_normal_not_found_result(self):
        result = self.ask(self.employee, {"question": self.EMPLOYEE_QUESTION, "config": "baseline",
                                          "updated_on_or_after": "2999-12-31"})
        self.assertEqual((result["status"], result["sources"], result["cutoff"]), ("not_found", [], "2999-12-31"))
        self.assertEqual(result["retrieval"]["candidates_considered"], 0)
        self.assertFalse(result["security_audit"]["violation"])

    def test_the_employee_server_never_returns_manager_content(self):
        result = self.ask(self.employee, {"question": self.MANAGER_ONLY_QUESTION, "config": "baseline"})
        self.assertEqual(result["role"], "employee")
        self.assertNotIn("manager_playbook", {s["corpus"] for s in result["sources"]})
        self.assertFalse(result["security_audit"]["violation"])

    def test_the_manager_server_reaches_the_manager_playbook(self):
        result = self.ask(self.manager, {"question": self.MANAGER_ONLY_QUESTION, "config": "baseline"})
        self.assertEqual(result["role"], "manager")
        self.assertIn("manager_playbook", {s["corpus"] for s in result["sources"]})
        self.assertFalse(result["security_audit"]["violation"])

    def test_a_request_cannot_choose_its_role(self):
        problem = self.assertProblem(self.employee.post("/v1/ask", {"question": self.MANAGER_ONLY_QUESTION,
                                                                    "role": "manager"}), 422, "validation-error")
        self.assertIn(["body", "role"], [e["location"] for e in problem["errors"]])

    def test_a_missing_collection_is_a_controlled_503_and_the_server_survives(self):
        # resolve_endpoint() raises SystemExit for an unknown collection: one read-only control-plane lookup.
        server = _ApiServer("employee", {"OPENSEARCH_COLLECTION": "novaops-collection-that-does-not-exist"})
        self.addCleanup(server.stop)
        self.assertProblem(server.post("/v1/ask", {"question": self.EMPLOYEE_QUESTION, "config": "baseline"},
                                       timeout=self.ASK_TIMEOUT), 503, "service-unavailable")
        code, _, text = server.request("GET", "/v1/health", timeout=120)
        self.assertEqual(code, 503)
        self.assertEqual(json.loads(text)["collection_state"], "MISSING")
        self.assertNotIn("does-not-exist", text)
        self.assertEqual(server.get("/healthz")[0], 200)
        self.assertIn("ask failed: service_unavailable (SystemExit)", server.output())
