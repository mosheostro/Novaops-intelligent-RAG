"""POST /v1/ask — the REST adapter over ask.ask(). In-process through FastAPI's
TestClient: ask.ask and every infrastructure entry point are patched, so no
network and no AWS. What is under test is the adapter: the request contract, that
the response is exactly the shared public projection, the failure mapping and the
HTTP boundary.
"""
import importlib.util
import json
import logging
import os
import unittest
from datetime import date
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

import api_server  # noqa: E402
import public_views  # noqa: E402
from models import (  # noqa: E402
    DEFAULT_CONFIG,
    AskResult,
    Candidate,
    LiveJudgement,
    RetrievalResult,
    SecurityAudit,
    SelectedChunk,
    SelectionResult,
)
from retrieval import UnsupportedAudienceError  # noqa: E402

BASE_URL = "http://127.0.0.1:8001"
JSON = {"Content-Type": "application/json"}
QUESTION = "How does PTO accrue? SENTINEL-QUESTION"
CHUNK_TEXT = "SENTINEL-CHUNK-TEXT"
MANAGER_SOURCE = "severance-SENTINEL.md"
GENERATED_ANSWER = "SENTINEL generated answer"
SECRET = "SENTINEL-SECRET arn:aws:aoss:us-east-1:123456789012:collection/abc"
JUDGEMENT = LiveJudgement(
    faithfulness=0.9, faithfulness_reason="SENTINEL faithfulness reason",
    context_relevance=0.8, context_relevance_reason="relevant",
    refused=False, completeness=0.7, completeness_reason="mostly complete",
)


def _candidate(source, audience="employee", rank=0, rerank_score=0.9):
    return Candidate(text=f"{CHUNK_TEXT} {source}", source=source,
                     corpus="handbook" if audience == "employee" else "manager_playbook",
                     audience=audience, subjects=["time_off_and_leave"], last_updated="2025-03-01",
                     vector_score=0.5, vector_rank=rank, rerank_score=rerank_score)


def _ask_result(status="selected", violation=False, judgement=None, role="employee", config="filter + rerank dynamic"):
    pool = [_candidate("pto.md"), _candidate("holidays.md", rank=1, rerank_score=0.6)]
    if violation:
        pool.append(_candidate(MANAGER_SOURCE, audience="manager", rank=2))
    chunks = [] if status in ("not_found", "access_violation") else [
        SelectedChunk(candidate=pool[1], final_rank=1), SelectedChunk(candidate=pool[0], final_rank=0)]
    return AskResult(
        question=QUESTION, audience=role, config=config, planned_subjects=["time_off_and_leave"],
        retrieval=RetrievalResult(
            audience=role, subjects_applied=["time_off_and_leave"], top_k_requested=10, candidates=pool,
            security=SecurityAudit(violation=violation, violating_sources=[MANAGER_SOURCE] if violation else []),
            cutoff=None),
        selection=SelectionResult(status=status, chunks=chunks,
                                  context_texts=[c.candidate.text for c in chunks] or ["not found"]),
        answer=GENERATED_ANSWER, judgement=judgement,
    )


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


class _AskTestCase(unittest.TestCase):
    role = "employee"

    def setUp(self):
        self.opensearch_client = patch("client.opensearch_client").start()
        self.aoss_client = patch("manage.aoss_client").start()
        self.ask = patch("ask.ask", return_value=_ask_result()).start()
        self.addCleanup(patch.stopall)
        self.client = TestClient(api_server.build_app(self.role), base_url=BASE_URL, raise_server_exceptions=False)

    def post(self, body, headers=JSON):
        content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return self.client.post("/v1/ask", content=content, headers=headers)

    def assertProblem(self, response, status: int, problem: str):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.headers["content-type"], "application/problem+json")
        self.assertEqual(response.json()["type"], f"urn:novaops:problem:{problem}")
        return response.json()

    def assertNothingProtected(self, response):
        for secret in (CHUNK_TEXT, "SENTINEL-QUESTION", "SENTINEL-SECRET", "arn:aws", "123456789012", "us-east-1"):
            self.assertNotIn(secret, response.text)
        for key in ("text", "context_texts", "vector_score", "vector_rank", "top_k_requested", "audience",
                    "violating_sources", "candidates", "question", "subjects_applied"):
            self.assertNotIn(key, _keys(response.json()))


class AskRequestTests(_AskTestCase):
    def test_a_valid_request_returns_the_shared_public_projection(self):
        response = self.post({"question": QUESTION})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.json(), public_views.project_ask_result(_ask_result()).model_dump(mode="json"))
        self.assertNothingProtected(response)

    def test_the_adapter_uses_the_shared_projection_function_itself(self):
        self.assertIs(api_server.project_ask_result, public_views.project_ask_result)
        self.assertIs(api_server.AskRagResult, public_views.AskRagResult)

    def test_defaults_and_the_stripped_question_reach_the_use_case(self):
        self.post({"question": "  How does PTO accrue?\n"})
        client_obj, question, role, config_name = self.ask.call_args.args
        self.assertIs(client_obj, self.opensearch_client.return_value)
        self.assertEqual((question, role, config_name), ("How does PTO accrue?", "employee", DEFAULT_CONFIG))
        self.assertEqual(self.ask.call_args.kwargs, {"judge": False, "cutoff": None})

    def test_explicit_config_judge_and_cutoff_are_passed_through(self):
        self.ask.return_value = _ask_result(judgement=JUDGEMENT, config="baseline")
        response = self.post({"question": "q", "config": "baseline", "judge": True,
                              "updated_on_or_after": "2025-04-28"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ask.call_args.args[3], "baseline")
        self.assertEqual(self.ask.call_args.kwargs, {"judge": True, "cutoff": date(2025, 4, 28)})

    def test_every_configuration_name_is_accepted(self):
        for name in ("baseline", "filter-only", "rerank-only", "filter + rerank static", "filter + rerank dynamic"):
            with self.subTest(config=name):
                self.assertEqual(self.post({"question": "q", "config": name}).status_code, 200)
                self.assertEqual(self.ask.call_args.args[3], name)

    def test_a_future_cutoff_and_an_explicit_null_are_valid(self):
        self.assertEqual(self.post({"question": "q", "updated_on_or_after": "2999-12-31"}).status_code, 200)
        self.assertEqual(self.ask.call_args.kwargs["cutoff"], date(2999, 12, 31))
        self.assertEqual(self.post({"question": "q", "updated_on_or_after": None}).status_code, 200)
        self.assertIsNone(self.ask.call_args.kwargs["cutoff"])

    def test_question_boundaries(self):
        for question, expected in (("hello", "hello"), ("x" * 2000, "x" * 2000), ("  padded  ", "padded")):
            with self.subTest(length=len(question)):
                self.assertEqual(self.post({"question": question}).status_code, 200)
                self.assertEqual(self.ask.call_args.args[1], expected)


class AskValidationTests(_AskTestCase):
    def assertRejected(self, body, location=None, headers=JSON):
        response = self.post(body, headers=headers)
        problem = self.assertProblem(response, 422, "validation-error")
        if location is not None:
            self.assertIn(location, [e["location"] for e in problem["errors"]])
        self.assertNotIn("SENTINEL", response.text)
        return problem

    def tearDown(self):
        self.ask.assert_not_called()
        self.opensearch_client.assert_not_called()  # the lazy client is not even created

    def test_the_question_must_be_a_real_non_blank_string_within_the_limit(self):
        for value, error_type in ((123, "string_type"), (True, "string_type"), (None, "string_type"),
                                  (["SENTINEL"], "string_type"), ({"q": "SENTINEL"}, "string_type"),
                                  ("", "string_too_short"), ("   \n\t", "string_too_short"),
                                  ("x" * 2001, "string_too_long")):
            with self.subTest(value=str(value)[:20]):
                problem = self.assertRejected({"question": value}, ["body", "question"])
                self.assertEqual([e["type"] for e in problem["errors"]], [error_type])

    def test_the_question_is_required(self):
        self.assertRejected({}, ["body", "question"])
        self.assertRejected({"config": "baseline"}, ["body", "question"])

    def test_role_is_not_part_of_the_contract(self):
        for role in ("manager", "employee", "SENTINEL"):
            with self.subTest(role=role):
                problem = self.assertRejected({"question": "q", "role": role}, ["body", "role"])
                self.assertEqual(problem["errors"][0]["type"], "extra_forbidden")

    def test_any_unknown_field_is_rejected(self):
        for field in ("audience", "top_k", "cutoff", "Question"):
            with self.subTest(field=field):
                self.assertRejected({"question": "q", field: "SENTINEL"}, ["body", field])

    def test_config_must_be_an_exact_configuration_name(self):
        for value in ("bogus", "Baseline", "filter_rerank_dynamic", "filter+rerank dynamic", " baseline", 1, None):
            with self.subTest(value=value):
                self.assertRejected({"question": "q", "config": value}, ["body", "config"])

    def test_judge_must_be_a_real_boolean(self):
        for value in ("true", "false", 1, 0, "yes", None, "SENTINEL"):
            with self.subTest(value=value):
                self.assertRejected({"question": "q", "judge": value}, ["body", "judge"])

    def test_the_cutoff_must_be_exactly_yyyy_mm_dd(self):
        for value in ("2025-1-1", "20250131", "2025-01-31T00:00:00", "2025-01-31 ", "31/01/2025", "not-a-date",
                      "2025-02-30", "2025-13-01", 1700000000, 20250131, True, ["2025-01-31"], "SENTINEL"):
            with self.subTest(value=value):
                self.assertRejected({"question": "q", "updated_on_or_after": value},
                                    ["body", "updated_on_or_after"])

    def test_the_body_must_be_one_json_object(self):
        for body in (b"", b"[]", b'["SENTINEL"]', b'"SENTINEL"', b"null", b"42", b"{not json SENTINEL",
                     b'{"question": "q"} trailing'):
            with self.subTest(body=body):
                self.assertRejected(body)


class AskResultTests(_AskTestCase):
    def test_not_found_is_a_normal_result(self):
        self.ask.return_value = _ask_result(status="not_found")
        response = self.post({"question": QUESTION})
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["status"], response.json()["sources"]), ("not_found", []))
        self.assertNothingProtected(response)

    def test_a_judged_result_carries_the_judgement(self):
        self.ask.return_value = _ask_result(judgement=JUDGEMENT)
        response = self.post({"question": QUESTION, "judge": True})
        self.assertEqual(response.json()["judgement"], JUDGEMENT.model_dump(mode="json"))

    def test_sources_are_public_provenance_only_ranked_from_one(self):
        sources = self.post({"question": QUESTION}).json()["sources"]
        self.assertEqual([(s["rank"], s["source"]) for s in sources], [(1, "pto.md"), (2, "holidays.md")])
        self.assertEqual(set(sources[0]), {"rank", "source", "corpus", "subjects", "last_updated", "rerank_score"})

    def test_a_security_violation_is_a_withheld_200_result_not_an_error(self):
        self.ask.return_value = _ask_result(violation=True, judgement=JUDGEMENT)
        response = self.post({"question": QUESTION, "judge": True})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["answer"], public_views.WITHHELD_ANSWER)
        self.assertEqual(body["sources"], [])
        self.assertIsNone(body["judgement"])
        self.assertEqual(body["security_audit"], {
            "violation": True, "violating_source_count": 1,
            "explanation": public_views.SECURITY_VIOLATION_EXPLANATION})
        for secret in (MANAGER_SOURCE, GENERATED_ANSWER, "SENTINEL faithfulness reason"):
            self.assertNotIn(secret, response.text)
        self.assertNothingProtected(response)


class ManagerServerTests(_AskTestCase):
    role = "manager"

    def test_the_servers_role_is_the_one_used(self):
        self.ask.return_value = _ask_result(role="manager")
        response = self.post({"question": "q"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ask.call_args.args[2], "manager")
        self.assertEqual(response.json()["role"], "manager")


class AskFailureTests(_AskTestCase):
    FAILURES = {
        "system_exit": (SystemExit(SECRET), 503, "service-unavailable"),
        "opensearch": (OpenSearchException(SECRET), 503, "service-unavailable"),
        "client_error": (ClientError({"Error": {"Code": "ThrottlingException", "Message": SECRET}}, "Converse"),
                         503, "service-unavailable"),
        "connection_timeout": (ConnectionTimeout("TIMEOUT", SECRET, Exception(SECRET)), 504, "service-timeout"),
        "read_timeout": (ReadTimeoutError(endpoint_url=SECRET), 504, "service-timeout"),
        "unsupported_role": (UnsupportedAudienceError(SECRET), 500, "server-misconfigured"),
        "unexpected": (RuntimeError(SECRET), 500, "internal-error"),
    }

    def test_each_use_case_failure_is_its_fixed_problem_without_details(self):
        for name, (error, status, problem) in self.FAILURES.items():
            with self.subTest(failure=name):
                self.ask.side_effect = error
                response = self.post({"question": QUESTION})
                self.assertProblem(response, status, problem)
                self.assertEqual(set(response.json()), {"type", "title", "status", "detail"})
                for leak in ("SENTINEL", "arn:aws", "123456789012", "us-east-1", "Throttling"):
                    self.assertNotIn(leak, response.text)

    def test_a_backend_system_exit_fails_one_request_and_the_next_one_succeeds(self):
        self.ask.side_effect = [SystemExit(SECRET), _ask_result()]
        self.assertProblem(self.post({"question": "q"}), 503, "service-unavailable")
        self.assertEqual(self.post({"question": "q"}).status_code, 200)
        self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_a_system_exit_while_creating_the_client_is_a_503_and_creation_is_retried(self):
        self.opensearch_client.side_effect = [SystemExit(SECRET), self.opensearch_client.return_value]
        self.assertProblem(self.post({"question": "q"}), 503, "service-unavailable")
        self.ask.assert_not_called()
        self.assertEqual(self.post({"question": "q"}).status_code, 200)
        self.assertEqual(self.opensearch_client.call_count, 2)

    def test_an_evaluation_only_status_never_leaves_the_server(self):
        self.ask.return_value = _ask_result(status="access_violation")
        response = self.post({"question": QUESTION})
        self.assertProblem(response, 500, "internal-error")
        self.assertNotIn("SENTINEL", response.text)


class AskBoundaryTests(_AskTestCase):
    def tearDown(self):
        self.ask.assert_not_called()

    def test_a_body_without_a_json_content_type_is_refused(self):
        for headers in ({}, {"Content-Type": "text/plain"}, {"Content-Type": "application/x-www-form-urlencoded"}):
            with self.subTest(headers=headers):
                self.assertProblem(self.post({"question": "q"}, headers=headers), 415, "unsupported-media-type")

    def test_a_foreign_host_is_refused(self):
        self.assertProblem(self.post({"question": "q"}, headers={**JSON, "Host": "evil.example"}), 400,
                           "invalid-host")

    def test_ask_only_accepts_post(self):
        response = self.client.get("/v1/ask")
        self.assertProblem(response, 405, "method-not-allowed")
        self.assertEqual(response.headers["allow"], "POST")


class LazyClientTests(_AskTestCase):
    def test_the_client_is_created_on_first_use_and_then_reused(self):
        self.opensearch_client.assert_not_called()  # building the app created nothing
        self.post({"question": "q"})
        self.post({"question": "q"})
        self.opensearch_client.assert_called_once()
        self.assertIs(self.ask.call_args_list[1].args[0], self.opensearch_client.return_value)

    def test_each_app_has_its_own_client(self):
        self.post({"question": "q"})
        other = TestClient(api_server.build_app("manager"), base_url=BASE_URL)
        other.post("/v1/ask", content=b'{"question": "q"}', headers=JSON)
        self.assertEqual(self.opensearch_client.call_count, 2)


class AskLoggingTests(_AskTestCase):
    def test_neither_the_question_nor_the_answer_is_logged(self):
        root = logging.getLogger()
        with self.assertLogs(root, level="DEBUG") as logs:
            logging.getLogger("api_server").warning("marker")  # assertLogs needs at least one record
            self.post({"question": QUESTION})
            self.ask.side_effect = SystemExit(SECRET)
            self.post({"question": QUESTION})
        rendered = "\n".join(logs.output)
        for secret in ("SENTINEL-QUESTION", GENERATED_ANSWER, "SENTINEL-SECRET"):
            self.assertNotIn(secret, rendered)


class AskOpenApiTests(_AskTestCase):
    def setUp(self):
        super().setUp()
        self.spec = self.client.get("/openapi.json").json()
        self.operation = self.spec["paths"]["/v1/ask"]["post"]

    def _schema(self, ref_holder):
        ref = ref_holder["$ref"]
        return self.spec["components"]["schemas"][ref.rsplit("/", 1)[1]]

    def test_ask_is_post_only(self):
        self.assertEqual(set(self.spec["paths"]["/v1/ask"]), {"post"})

    def test_the_request_contract_has_no_role_and_forbids_unknown_fields(self):
        body = self.operation["requestBody"]
        self.assertTrue(body["required"])
        request = self._schema(body["content"]["application/json"]["schema"])
        self.assertEqual(set(request["properties"]), {"question", "config", "judge", "updated_on_or_after"})
        self.assertEqual(request["required"], ["question"])
        self.assertIs(request["additionalProperties"], False)
        self.assertEqual((request["properties"]["question"]["minLength"],
                          request["properties"]["question"]["maxLength"]), (1, 2000))

    def test_the_success_response_is_the_shared_projection(self):
        ok = self.operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(ok["$ref"].rsplit("/", 1)[1], "AskRagResult")
        properties = set(self._schema(ok)["properties"])
        self.assertEqual(properties, set(public_views.AskRagResult.model_fields))

    def test_error_responses_are_documented_as_problems(self):
        for status in ("415", "422", "500", "503", "504"):
            with self.subTest(status=status):
                content = self.operation["responses"][status]["content"]
                self.assertEqual(list(content), ["application/problem+json"])
                self.assertEqual(content["application/problem+json"]["schema"]["$ref"].rsplit("/", 1)[1],
                                 "Problem")
        self.assertNotIn("HTTPValidationError", self.spec["components"]["schemas"])

    def test_the_documented_problem_schema_matches_the_problems_actually_returned(self):
        schemas = self.spec["components"]["schemas"]
        documented = set(schemas["Problem"]["properties"])
        documented_field_error = set(schemas["ProblemFieldError"]["properties"])
        self.assertEqual(documented, {"type", "title", "status", "detail", "errors"})
        self.assertEqual(set(schemas["Problem"]["required"]), {"type", "title", "status", "detail"})

        self.ask.side_effect = [SystemExit(SECRET), RuntimeError(SECRET)]
        responses = {
            "validation": self.post({"question": 7, "role": "manager"}),
            "media_type": self.post({"question": "q"}, headers={"Content-Type": "text/plain"}),
            "unavailable": self.post({"question": "q"}),
            "internal": self.post({"question": "q"}),
            "not_found": self.client.get("/v1/nope"),
            "method": self.client.get("/v1/ask"),
            "host": self.client.get("/healthz", headers={"Host": "evil.example"}),
        }
        for name, response in responses.items():
            with self.subTest(problem=name):
                self.assertEqual(response.headers["content-type"], "application/problem+json")
                body = response.json()
                self.assertTrue({"type", "title", "status", "detail"} <= set(body))
                self.assertLessEqual(set(body), documented)  # no undocumented public field
                self.assertEqual(body["status"], response.status_code)
                self.assertEqual("errors" in body, name == "validation")  # errors only where applicable
                for error in body.get("errors", []):
                    self.assertEqual(set(error), documented_field_error)


if __name__ == "__main__":
    unittest.main()
