"""mcp_server.py — the MCP adapter. Driven through the SDK's in-memory client, so
no subprocess, no network and no AWS: infrastructure entry points are patched and
must never be reached by what these tests exercise.

Needs the optional `mcp` dependency (requirements-mcp.txt). Without it the whole
module is skipped with an explicit reason — the dependency-boundary tests in
test_mcp_boundary.py still run either way.
"""
import importlib.util
import io
import json
import os
import re
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

if importlib.util.find_spec("mcp") is None:
    raise unittest.SkipTest("MCP tests need the optional dependency: pip install -r requirements-mcp.txt")

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from datetime import date  # noqa: E402

import anyio  # noqa: E402
from botocore.exceptions import ClientError, NoCredentialsError, ReadTimeoutError  # noqa: E402
from mcp import Client  # noqa: E402
from opensearchpy.exceptions import ConnectionTimeout, OpenSearchException  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import config  # noqa: E402
import mcp_server  # noqa: E402
from manage import CollectionHealth  # noqa: E402
from eval import MIN_RERANK_SCORE, PLANNED_CONFIGS  # noqa: E402
from models import (  # noqa: E402
    CONFIG_NAMES,
    DEFAULT_CONFIG,
    AskResult,
    Candidate,
    LiveJudgement,
    RetrievalResult,
    SecurityAudit,
    SelectedChunk,
    SelectionResult,
)
from retrieval import SUPPORTED_AUDIENCES, UnsupportedAudienceError  # noqa: E402
from subjects import SUBJECTS  # noqa: E402

INVALID_ROLES = ("user", "boss", "board", "whatever", "", "Employee", " employee")
TUNING_KEYS = ("top_k", "pool", "baseline_top_k", "candidate_pool_size", "rerank_static_top_k", "min_rerank_score")


def _call(server, action):
    """Run `action(client)` against `server` over the SDK's in-memory transport."""
    async def run():
        async with Client(server) as c:
            return await action(c)
    return anyio.run(run)


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


class _InfrastructureGuard(unittest.TestCase):
    """Every infrastructure entry point is patched; tests assert they stay unused."""

    def setUp(self):
        self.opensearch_client = patch("client.opensearch_client").start()
        self.aoss_client = patch("manage.aoss_client").start()
        self.ask = patch("ask.ask").start()
        self.addCleanup(patch.stopall)

    def assertNoInfrastructureCall(self):
        for mock in (self.opensearch_client, self.aoss_client, self.ask):
            mock.assert_not_called()


class RegistrationTests(_InfrastructureGuard):
    def test_exactly_the_registered_surface(self):
        server = mcp_server.build_server("employee")
        tools, resources, templates, prompts = _call(server, lambda c: _gather(
            c.list_tools(), c.list_resources(), c.list_resource_templates(), c.list_prompts()))
        self.assertEqual({t.name for t in tools.tools}, {"get_rag_capabilities", "ask_rag", "health_check"})
        self.assertEqual({str(r.uri) for r in resources.resources}, {"rag://subjects"})
        self.assertEqual(templates.resource_templates, [])
        self.assertEqual(prompts.prompts, [])
        self.assertNoInfrastructureCall()

    def test_capabilities_tool_takes_no_arguments_and_declares_an_output_schema(self):
        tools = _call(mcp_server.build_server("employee"), lambda c: c.list_tools())
        tool = next(t for t in tools.tools if t.name == "get_rag_capabilities")
        self.assertEqual(tool.input_schema.get("properties", {}), {})
        self.assertTrue(tool.output_schema)


async def _gather(*coros):
    return [await c for c in coros]


class RoleStartupTests(_InfrastructureGuard):
    def test_supported_roles_build_a_server(self):
        for role in sorted(SUPPORTED_AUDIENCES):
            with self.subTest(role=role):
                self.assertIsNotNone(mcp_server.build_server(role))

    def test_unsupported_role_never_builds_a_server(self):
        with patch("mcp_server.MCPServer") as server_class:
            for role in INVALID_ROLES:
                with self.subTest(role=role), self.assertRaises(UnsupportedAudienceError):
                    mcp_server.build_server(role)
            server_class.assert_not_called()

    def test_main_refuses_an_unsupported_role_on_stderr_only(self):
        with patch("mcp_server.MCPServer") as server_class:
            for role in INVALID_ROLES:
                with self.subTest(role=role):
                    out, err = io.StringIO(), io.StringIO()
                    with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as exit_:
                        mcp_server.main(["--role", role])
                    self.assertEqual(exit_.exception.code, 2)
                    self.assertEqual(out.getvalue(), "")
                    self.assertIn("unsupported role", err.getvalue())
            server_class.assert_not_called()

    def test_main_requires_the_role_argument(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as exit_:
            mcp_server.main([])
        self.assertEqual(exit_.exception.code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("--role", err.getvalue())

    def test_main_runs_the_validated_server_over_stdio(self):
        server = MagicMock()
        with patch("mcp_server.build_server", return_value=server) as build:
            mcp_server.main(["--role", "manager"])
        build.assert_called_once_with("manager")
        server.run.assert_called_once_with("stdio")
        self.assertNoInfrastructureCall()

    def test_ctrl_c_stops_the_server_quietly(self):
        # A manually started server is stopped with Ctrl+C: no traceback, nothing on stdout.
        server = MagicMock()
        server.run.side_effect = KeyboardInterrupt
        out, err = io.StringIO(), io.StringIO()
        with patch("mcp_server.build_server", return_value=server), redirect_stdout(out), redirect_stderr(err):
            mcp_server.main(["--role", "manager"])  # returns normally instead of raising
        self.assertEqual(out.getvalue(), "")
        self.assertNotIn("Traceback", err.getvalue())


class CapabilitiesTests(_InfrastructureGuard):
    def _capabilities(self, role="employee") -> dict:
        result = _call(mcp_server.build_server(role), lambda c: c.call_tool("get_rag_capabilities", {}))
        self.assertFalse(result.is_error)
        return result.structured_content

    def test_tool_returns_the_capabilities_built_for_the_configured_role(self):
        for role in sorted(SUPPORTED_AUDIENCES):
            with self.subTest(role=role):
                caps = self._capabilities(role)
                self.assertEqual(caps, mcp_server.build_capabilities(role).model_dump(mode="json"))
                self.assertEqual(caps["role"]["configured"], role)
        self.assertNoInfrastructureCall()

    def test_derived_from_canonical_sources(self):
        caps = mcp_server.build_capabilities("employee")
        self.assertEqual(caps.contract_version, 1)
        self.assertEqual([c.name for c in caps.configurations], list(CONFIG_NAMES))
        self.assertEqual(caps.default_configuration, DEFAULT_CONFIG)
        self.assertEqual(caps.role.supported, sorted(SUPPORTED_AUDIENCES))
        self.assertEqual(caps.subjects, list(SUBJECTS))
        self.assertEqual(caps.subjects_resource, "rag://subjects")
        self.assertEqual(caps.options.question_max_chars, mcp_server.MAX_QUESTION_CHARS)
        self.assertEqual(mcp_server.MAX_QUESTION_CHARS, 2000)
        self.assertEqual(caps.judgement.parameter, "judge")
        self.assertFalse(caps.judgement.default)
        self.assertEqual(caps.judgement.judges,
                         ["faithfulness", "context_relevance", "context_completeness", "refusal"])

    def test_configuration_semantics_agree_with_the_pipeline(self):
        for c in mcp_server.build_capabilities("employee").configurations:
            with self.subTest(config=c.name):
                self.assertEqual(c.subject_filter, c.name in PLANNED_CONFIGS)
                self.assertEqual(c.reranking, c.context_selection != "all_retrieved")
                self.assertTrue(c.summary)

    def test_role_is_described_as_a_server_role_not_authentication(self):
        note = mcp_server.build_capabilities("manager").role.note.lower()
        self.assertIn("not authentication", note)
        self.assertIn("startup", note)

    def test_no_internal_tuning_parameters(self):
        caps = mcp_server.build_capabilities("employee").model_dump(mode="json")
        for key in _keys(caps):
            for tuning in TUNING_KEYS:
                self.assertNotIn(tuning, key)
        self.assertNotIn(str(MIN_RERANK_SCORE), json.dumps(caps))

    def test_models_are_frozen(self):
        caps = mcp_server.build_capabilities("employee")
        with self.assertRaises(ValidationError):
            caps.contract_version = 2
        with self.assertRaises(ValidationError):
            caps.role.configured = "manager"


class SubjectsResourceTests(_InfrastructureGuard):
    def test_static_json_list_of_the_canonical_subjects(self):
        result = _call(mcp_server.build_server("employee"), lambda c: c.read_resource("rag://subjects"))
        (content,) = result.contents
        self.assertEqual(content.mime_type, "application/json")
        self.assertEqual(json.loads(content.text), {"subjects": list(SUBJECTS)})
        self.assertNoInfrastructureCall()


class ProtocolMetadataTests(_InfrastructureGuard):
    """initialize -> serverInfo / instructions is protocol output every client sees;
    it must not carry an infrastructure identifier either."""

    async def _initialize(self, c):
        return c.server_info, c.instructions

    def test_server_name_is_the_neutral_public_name(self):
        info, _ = _call(mcp_server.build_server("employee"), self._initialize)
        self.assertEqual(info.name, "novaops-knowledge-base")

    def test_server_info_never_carries_the_configured_collection(self):
        for collection in ("test-kb-collection-7f3a", "novaops-knowledge-base-collection"):
            with self.subTest(collection=collection), patch.object(config, "OPENSEARCH_COLLECTION", collection), \
                    patch.dict(os.environ, {"OPENSEARCH_COLLECTION": collection}):
                info, instructions = _call(mcp_server.build_server("employee"), self._initialize)
                self.assertNotEqual(info.name, collection)
                self.assertNotIn(collection, info.name)
                self.assertNotIn(collection, info.model_dump_json() + (instructions or ""))

    def test_server_info_reveals_no_private_infrastructure(self):
        info, instructions = _call(mcp_server.build_server("employee"), self._initialize)
        rendered = info.model_dump_json() + (instructions or "")
        for secret in (config.OPENSEARCH_COLLECTION, config.AWS_REGION, "aoss", "amazonaws", "endpoint",
                       "novaops-kb"):
            self.assertNotIn(secret, rendered)
        self.assertIsNone(re.search(r"\b\d{12}\b", rendered))


class LeakGuardTests(_InfrastructureGuard):
    def test_capabilities_and_resource_reveal_no_private_infrastructure(self):
        server = mcp_server.build_server("employee")
        caps, resource = _call(server, lambda c: _gather(
            c.call_tool("get_rag_capabilities", {}), c.read_resource("rag://subjects")))
        rendered = json.dumps(caps.structured_content) + caps.content[0].text + resource.contents[0].text
        for secret in (config.OPENSEARCH_COLLECTION, config.AWS_REGION, os.environ["AWS_ACCESS_KEY_ID"],
                       "aoss", "amazonaws", "endpoint", "novaops-kb"):
            self.assertNotIn(secret, rendered)
        self.assertIsNone(re.search(r"\b\d{12}\b", rendered))  # no AWS account ids

    def test_building_and_using_the_server_writes_nothing_to_stdout(self):
        out = io.StringIO()
        with redirect_stdout(out):
            server = mcp_server.build_server("employee")
            _call(server, lambda c: _gather(c.call_tool("get_rag_capabilities", {}),
                                            c.read_resource("rag://subjects")))
        self.assertEqual(out.getvalue(), "")


HR_TEXT = "SENTINEL-CHUNK-TEXT-handbook PTO accrues monthly."
POLICY_TEXT = "SENTINEL-CHUNK-TEXT-policy Holidays are listed yearly."
MANAGER_TEXT = "SENTINEL-CHUNK-TEXT-manager Severance bands by tenure."
GENERATED_ANSWER = "SENTINEL-GENERATED-ANSWER PTO accrues monthly."
MANAGER_SOURCE = "SENTINEL-manager-only-severance.md"


def _candidate(text, source, audience="all", rerank=None, rank=0):
    return Candidate(text=text, source=source, corpus="handbook" if audience == "all" else "manager_playbook",
                     audience=audience, subjects=["time_off_and_leave"], last_updated="2025-03-01",
                     vector_score=0.87, vector_rank=rank, rerank_score=rerank)


def _ask_result(*, violation=False, judgement=None, status="selected", role="employee",
                config_name="filter + rerank dynamic") -> AskResult:
    hr = _candidate(HR_TEXT, "pto.md", rerank=0.9, rank=0)
    policy = _candidate(POLICY_TEXT, "holidays.md", rerank=0.7, rank=1)
    pool = [hr, policy]
    violating = []
    if violation:
        pool.append(_candidate(MANAGER_TEXT, MANAGER_SOURCE, audience="manager", rerank=0.8, rank=2))
        violating = [MANAGER_SOURCE]
    if status == "selected":
        # Domain final_rank is 0-based, as the real pipeline produces it. Deliberately
        # out of final_rank order: the projection must sort.
        chunks = [SelectedChunk(candidate=policy, final_rank=1), SelectedChunk(candidate=hr, final_rank=0)]
        if violation:
            chunks.append(SelectedChunk(candidate=pool[2], final_rank=2))
        selection = SelectionResult(status="selected", chunks=chunks, context_texts=[c.candidate.text for c in chunks])
    else:
        selection = SelectionResult(status=status, chunks=[],
                                    context_texts=["not found"] if status == "not_found" else [])
    retrieval = RetrievalResult(
        audience=role, subjects_applied=["time_off_and_leave"], top_k_requested=10, candidates=pool,
        security=SecurityAudit(violation=violation, violating_sources=violating), cutoff=date(2025, 1, 1),
    )
    return AskResult(question="How does PTO accrue?", audience=role, config=config_name,
                     planned_subjects=["time_off_and_leave"], retrieval=retrieval, selection=selection,
                     answer=GENERATED_ANSWER, judgement=judgement)


JUDGEMENT = LiveJudgement(faithfulness=0.9, faithfulness_reason="grounded", context_relevance=1.0,
                          context_relevance_reason="on topic", refused=False, completeness=0.8,
                          completeness_reason="mostly complete")


class AskRagSchemaTests(_InfrastructureGuard):
    def setUp(self):
        super().setUp()
        tools = _call(mcp_server.build_server("employee"), lambda c: c.list_tools())
        self.tool = next(t for t in tools.tools if t.name == "ask_rag")
        self.props = self.tool.input_schema["properties"]

    def test_exactly_four_arguments_only_question_required_and_no_role(self):
        self.assertEqual(set(self.props), {"question", "config", "judge", "updated_on_or_after"})
        self.assertEqual(self.tool.input_schema.get("required"), ["question"])
        self.assertNotIn("role", self.props)

    def test_question_length_bounds(self):
        self.assertEqual(self.props["question"]["minLength"], 1)
        self.assertEqual(self.props["question"]["maxLength"], mcp_server.MAX_QUESTION_CHARS)

    def test_config_is_the_canonical_enum_with_the_shared_default(self):
        self.assertEqual(self.props["config"]["enum"], list(CONFIG_NAMES))
        self.assertEqual(self.props["config"]["default"], DEFAULT_CONFIG)

    def test_judge_defaults_off_and_cutoff_is_an_optional_date(self):
        self.assertIs(self.props["judge"]["default"], False)
        cutoff = self.props["updated_on_or_after"]
        self.assertIsNone(cutoff.get("default"))
        self.assertIn({"type": "string", "format": "date"}, cutoff["anyOf"])

    def test_cutoff_describes_its_iso_format(self):
        # Clients such as MCP Inspector render this as a plain text box; the description is the hint.
        self.assertIn("YYYY-MM-DD", self.props["updated_on_or_after"]["description"])

    def test_declares_an_output_schema(self):
        self.assertTrue(self.tool.output_schema)


class AskRagInputTests(_InfrastructureGuard):
    def setUp(self):
        super().setUp()
        self.ask.return_value = _ask_result()

    def _ask(self, args, role="employee"):
        return _call(mcp_server.build_server(role), lambda c: c.call_tool("ask_rag", args))

    def test_invalid_arguments_are_rejected_before_the_use_case(self):
        for args in ({"question": ""}, {"question": "   "}, {"question": "x" * 2001},
                     {"question": "q", "config": "bogus"}, {"question": "q", "config": "filter_rerank_dynamic"},
                     {"question": "q", "updated_on_or_after": "not-a-date"}, {}):
            with self.subTest(args=args):
                self.assertTrue(self._ask(args).is_error)
        self.ask.assert_not_called()
        self.opensearch_client.assert_not_called()

    def test_maximum_length_is_accepted(self):
        self.assertFalse(self._ask({"question": "x" * 2000}).is_error)
        self.assertEqual(self.ask.call_args.args[1], "x" * 2000)

    def test_question_is_stripped_and_defaults_apply(self):
        self._ask({"question": "  How does PTO accrue?\n"})
        client_obj, question, role, config_name = self.ask.call_args.args
        self.assertIs(client_obj, self.opensearch_client.return_value)
        self.assertEqual((question, role, config_name), ("How does PTO accrue?", "employee", DEFAULT_CONFIG))
        self.assertEqual(self.ask.call_args.kwargs, {"judge": False, "cutoff": None})

    def test_explicit_config_judge_and_cutoff_are_passed_through(self):
        self.ask.return_value = _ask_result(judgement=JUDGEMENT, config_name="baseline")
        self._ask({"question": "q", "config": "baseline", "judge": True, "updated_on_or_after": "2025-04-28"})
        self.assertEqual(self.ask.call_args.args[3], "baseline")
        self.assertEqual(self.ask.call_args.kwargs, {"judge": True, "cutoff": date(2025, 4, 28)})

    def test_the_configured_role_is_used_and_cannot_be_overridden_by_the_client(self):
        for role in sorted(SUPPORTED_AUDIENCES):
            with self.subTest(role=role):
                self.ask.reset_mock()
                result = self._ask({"question": "q", "role": "manager" if role == "employee" else "employee"},
                                   role=role)
                if not result.is_error:  # an unknown argument is either rejected or ignored — never honored
                    self.assertEqual(self.ask.call_args.args[2], role)


class ProjectionTests(unittest.TestCase):
    def test_selected_answer_maps_to_the_public_fields(self):
        p = mcp_server.project_ask_result(_ask_result())
        self.assertEqual(p.answer, GENERATED_ANSWER)
        self.assertEqual((p.config, p.role, p.status), ("filter + rerank dynamic", "employee", "selected"))
        self.assertEqual(p.planned_subjects, ["time_off_and_leave"])
        self.assertEqual(p.cutoff, date(2025, 1, 1))
        self.assertEqual(p.retrieval.candidates_considered, 2)
        self.assertEqual([(s.rank, s.source) for s in p.sources], [(1, "pto.md"), (2, "holidays.md")])
        self.assertEqual(p.sources[0].model_dump(), {
            "rank": 1, "source": "pto.md", "corpus": "handbook", "subjects": ["time_off_and_leave"],
            "last_updated": "2025-03-01", "rerank_score": 0.9})
        self.assertEqual(p.security_audit.model_dump(),
                         {"violation": False, "violating_source_count": 0, "explanation": None})
        self.assertIsNone(p.judgement)

    def test_public_rank_is_one_based_and_follows_final_rank(self):
        r = _ask_result()
        by_final_rank = sorted(r.selection.chunks, key=lambda c: c.final_rank)
        self.assertEqual([c.final_rank for c in by_final_rank], [0, 1])  # the domain stays 0-based
        p = mcp_server.project_ask_result(r)
        self.assertEqual(p.sources[0].rank, 1)
        self.assertEqual(p.sources[1].rank, 2)
        self.assertEqual([s.source for s in p.sources], [c.candidate.source for c in by_final_rank])
        self.assertEqual([c.final_rank for c in r.selection.chunks], [1, 0])  # input not mutated

    def test_no_chunk_text_or_internal_fields_are_exposed(self):
        dumped = mcp_server.project_ask_result(_ask_result(judgement=JUDGEMENT)).model_dump(mode="json")
        rendered = json.dumps(dumped)
        for text in (HR_TEXT, POLICY_TEXT, "SENTINEL-CHUNK-TEXT", "How does PTO accrue?"):
            self.assertNotIn(text, rendered)
        for key in ("text", "context_texts", "vector_score", "vector_rank", "top_k_requested", "audience",
                    "violating_sources", "candidates", "question"):
            self.assertNotIn(key, _keys(dumped))

    def test_not_found_has_no_sources(self):
        p = mcp_server.project_ask_result(_ask_result(status="not_found"))
        self.assertEqual((p.status, p.sources), ("not_found", []))
        self.assertFalse(p.security_audit.violation)

    def test_judgement_is_projected_unchanged_when_present(self):
        p = mcp_server.project_ask_result(_ask_result(judgement=JUDGEMENT))
        self.assertEqual(p.judgement, JUDGEMENT)

    def test_access_violation_status_never_leaves_the_server(self):
        with self.assertRaises(RuntimeError):
            mcp_server.project_ask_result(_ask_result(status="access_violation"))

    def test_models_are_frozen(self):
        p = mcp_server.project_ask_result(_ask_result())
        with self.assertRaises(ValidationError):
            p.answer = "changed"
        with self.assertRaises(ValidationError):
            p.security_audit.violation = True


class SecurityViolationProjectionTests(unittest.TestCase):
    def setUp(self):
        self.p = mcp_server.project_ask_result(_ask_result(violation=True, judgement=JUDGEMENT))

    def test_answer_sources_and_judgement_are_withheld(self):
        self.assertEqual(self.p.answer, mcp_server.WITHHELD_ANSWER)
        self.assertEqual(self.p.sources, [])
        self.assertIsNone(self.p.judgement)

    def test_audit_reports_the_count_and_a_fixed_explanation(self):
        self.assertEqual(self.p.security_audit.model_dump(), {
            "violation": True, "violating_source_count": 1,
            "explanation": mcp_server.SECURITY_VIOLATION_EXPLANATION})

    def test_nothing_protected_is_disclosed(self):
        rendered = json.dumps(self.p.model_dump(mode="json"))
        for secret in (MANAGER_SOURCE, MANAGER_TEXT, HR_TEXT, GENERATED_ANSWER, "SENTINEL", "grounded"):
            self.assertNotIn(secret, rendered)

    def test_fixed_wording_names_the_rule_category_only(self):
        for wording in (mcp_server.WITHHELD_ANSWER, mcp_server.SECURITY_VIOLATION_EXPLANATION):
            self.assertNotRegex(wording, r"\.md\b|manager_playbook|handbook")
        self.assertIn("Access-control audit failed", mcp_server.SECURITY_VIOLATION_EXPLANATION)

    def test_non_content_metadata_is_kept(self):
        self.assertEqual((self.p.config, self.p.role, self.p.status), ("filter + rerank dynamic", "employee",
                                                                      "selected"))
        self.assertEqual(self.p.retrieval.candidates_considered, 3)
        self.assertEqual(self.p.planned_subjects, ["time_off_and_leave"])


class AskRagToolTests(_InfrastructureGuard):
    def _ask(self, args=None, server=None):
        server = server or mcp_server.build_server("employee")
        return _call(server, lambda c: c.call_tool("ask_rag", args or {"question": "How does PTO accrue?"}))

    def test_returns_the_projection_as_structured_content(self):
        self.ask.return_value = _ask_result(judgement=JUDGEMENT)
        result = self._ask({"question": "How does PTO accrue?", "judge": True})
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content,
                         mcp_server.project_ask_result(_ask_result(judgement=JUDGEMENT)).model_dump(mode="json"))

    def test_judgement_is_null_when_not_requested(self):
        self.ask.return_value = _ask_result()
        self.assertIsNone(self._ask().structured_content["judgement"])
        self.assertIs(self.ask.call_args.kwargs["judge"], False)

    def test_security_violation_is_a_withheld_result_not_an_error(self):
        self.ask.return_value = _ask_result(violation=True, judgement=JUDGEMENT)
        result = self._ask()
        self.assertFalse(result.is_error)
        rendered = json.dumps(result.structured_content) + result.content[0].text
        self.assertEqual(result.structured_content["answer"], mcp_server.WITHHELD_ANSWER)
        for secret in (MANAGER_SOURCE, MANAGER_TEXT, GENERATED_ANSWER):
            self.assertNotIn(secret, rendered)

    def test_writes_nothing_to_stdout(self):
        self.ask.return_value = _ask_result()
        out = io.StringIO()
        with redirect_stdout(out):
            self._ask()
        self.assertEqual(out.getvalue(), "")

    def test_rendered_output_reveals_no_private_infrastructure(self):
        self.ask.return_value = _ask_result(judgement=JUDGEMENT)
        result = self._ask({"question": "q", "judge": True})
        rendered = json.dumps(result.structured_content) + result.content[0].text
        for secret in (config.OPENSEARCH_COLLECTION, config.AWS_REGION, "aoss", "amazonaws", "endpoint"):
            self.assertNotIn(secret, rendered)
        self.assertIsNone(re.search(r"\b\d{12}\b", rendered))


SECRET = "Collection 'SECRET-COLLECTION' at https://abc123.us-east-1.aoss.amazonaws.com account 123456789012"
EXPECTED_TOOL_ERRORS = [
    (UnsupportedAudienceError(SECRET), "unsupported_role: the server's configured role is not supported."),
    (OpenSearchException(SECRET), "service_unavailable: the knowledge base or model service is unavailable. "
                                  "Try again later."),
    (ClientError({"Error": {"Code": "AccessDeniedException", "Message": SECRET}}, "Converse"),
     "service_unavailable: the knowledge base or model service is unavailable. Try again later."),
    (NoCredentialsError(), "service_unavailable: the knowledge base or model service is unavailable. "
                           "Try again later."),
    (SystemExit(SECRET), "service_unavailable: the knowledge base or model service is unavailable. "
                         "Try again later."),
    (ConnectionTimeout("TIMEOUT", SECRET, Exception()), "service_timeout: the knowledge base did not respond "
                                                        "in time; it may be warming up. Retry shortly."),
    (ReadTimeoutError(endpoint_url="https://abc123.aoss.amazonaws.com"),
     "service_timeout: the knowledge base did not respond in time; it may be warming up. Retry shortly."),
]


class AskRagErrorTests(_InfrastructureGuard):
    def _ask_error(self, server=None):
        server = server or mcp_server.build_server("employee")
        result = _call(server, lambda c: c.call_tool("ask_rag", {"question": "q"}))
        self.assertTrue(result.is_error)
        return result.content[0].text

    def assertNoSecret(self, text):
        for secret in ("SECRET", "aoss", "amazonaws", "123456789012", "us-east-1"):
            self.assertNotIn(secret, text)

    def test_each_failure_category_becomes_its_fixed_tool_error(self):
        for exc, message in EXPECTED_TOOL_ERRORS:
            with self.subTest(exc=type(exc).__name__):
                self.ask.side_effect = exc
                text = self._ask_error()
                self.assertEqual(text, f"Error executing tool ask_rag: {message}")
                self.assertNoSecret(text)

    def test_unexpected_exceptions_are_reported_generically(self):
        for exc in (RuntimeError(SECRET), ValueError(SECRET), KeyError(SECRET)):
            with self.subTest(exc=type(exc).__name__):
                self.ask.side_effect = exc
                text = self._ask_error()
                self.assertEqual(text, "Error executing tool ask_rag")

    def test_server_survives_system_exit_and_answers_the_next_call(self):
        self.ask.side_effect = [SystemExit(SECRET), _ask_result()]
        server = mcp_server.build_server("employee")
        first, second = _call(server, lambda c: _gather(c.call_tool("ask_rag", {"question": "q"}),
                                                          c.call_tool("ask_rag", {"question": "q"})))
        self.assertTrue(first.is_error)
        self.assertNoSecret(first.content[0].text)
        self.assertFalse(second.is_error)
        self.assertEqual(second.structured_content["answer"], GENERATED_ANSWER)


class AskRagLazyClientTests(_InfrastructureGuard):
    def test_client_is_created_on_first_question_and_then_reused(self):
        self.ask.return_value = _ask_result()
        server = mcp_server.build_server("employee")
        _call(server, lambda c: c.list_tools())
        self.opensearch_client.assert_not_called()
        _call(server, lambda c: _gather(c.call_tool("ask_rag", {"question": "a"}),
                                        c.call_tool("ask_rag", {"question": "b"})))
        self.opensearch_client.assert_called_once_with()

    def test_failed_client_creation_is_a_service_error_and_is_retried(self):
        sentinel = object()
        self.opensearch_client.side_effect = [SystemExit(SECRET), sentinel]
        self.ask.return_value = _ask_result()
        server = mcp_server.build_server("employee")
        first, second = _call(server, lambda c: _gather(c.call_tool("ask_rag", {"question": "q"}),
                                                          c.call_tool("ask_rag", {"question": "q"})))
        self.assertTrue(first.is_error)
        self.assertIn("service_unavailable", first.content[0].text)
        self.assertNotIn("SECRET", first.content[0].text)
        self.assertFalse(second.is_error)
        self.ask.assert_called_once()
        self.assertIs(self.ask.call_args.args[0], sentinel)


SECRET_ENDPOINT = "https://SECRET-abc123.us-east-1.aoss.amazonaws.com"


def _health(status="ACTIVE", index_exists=True, chunk_count=400, data_plane_error=None, endpoint=SECRET_ENDPOINT):
    return CollectionHealth(status=status, endpoint=endpoint, index_exists=index_exists, chunk_count=chunk_count,
                            data_plane_error=data_plane_error)


HEALTH_CASES = {  # name -> (CollectionHealth, expected HealthResult fields)
    "healthy": (_health(), dict(ready=True, collection_state="ACTIVE", index_present=True, chunk_count=400,
                                data_plane_reachable=True)),
    "missing collection": (_health(status=None, index_exists=None, chunk_count=None, endpoint=None),
                           dict(ready=False, collection_state="MISSING", index_present=None, chunk_count=None,
                                data_plane_reachable=None)),
    "not active": (_health(status="CREATING", index_exists=None, chunk_count=None),
                   dict(ready=False, collection_state="CREATING", index_present=None, chunk_count=None,
                        data_plane_reachable=None)),
    "missing index": (_health(index_exists=False, chunk_count=None),
                      dict(ready=False, collection_state="ACTIVE", index_present=False, chunk_count=None,
                           data_plane_reachable=True)),
    "zero chunks": (_health(chunk_count=0),
                    dict(ready=False, collection_state="ACTIVE", index_present=True, chunk_count=0,
                         data_plane_reachable=True)),
    "data plane failure": (_health(index_exists=None, chunk_count=None, data_plane_error=f"timeout at {SECRET_ENDPOINT}"),
                           dict(ready=False, collection_state="ACTIVE", index_present=None, chunk_count=None,
                                data_plane_reachable=False)),
}


class HealthProjectionTests(unittest.TestCase):
    def test_every_health_state_maps_to_its_public_result(self):
        for name, (health, expected) in HEALTH_CASES.items():
            with self.subTest(case=name):
                self.assertEqual(mcp_server.project_health(health).model_dump(), expected)

    def test_endpoint_and_error_text_are_never_projected(self):
        for name, (health, _expected) in HEALTH_CASES.items():
            with self.subTest(case=name):
                rendered = json.dumps(mcp_server.project_health(health).model_dump(mode="json"))
                self.assertNotIn("SECRET", rendered)
                self.assertNotIn("timeout", rendered)

    def test_model_is_frozen(self):
        with self.assertRaises(ValidationError):
            mcp_server.project_health(_health()).ready = False


class HealthCheckToolTests(_InfrastructureGuard):
    def setUp(self):
        super().setUp()
        self.collection_health = patch("manage.collection_health").start()

    def _check(self, server=None):
        return _call(server or mcp_server.build_server("employee"), lambda c: c.call_tool("health_check", {}))

    def test_schema_takes_no_arguments_and_declares_the_health_output(self):
        tools = _call(mcp_server.build_server("employee"), lambda c: c.list_tools())
        tool = next(t for t in tools.tools if t.name == "health_check")
        self.assertEqual(tool.input_schema.get("properties", {}), {})
        self.assertEqual(set(tool.output_schema["properties"]),
                         {"ready", "collection_state", "index_present", "chunk_count", "data_plane_reachable"})

    def test_reports_each_state_through_the_existing_use_case(self):
        for name, (health, expected) in HEALTH_CASES.items():
            with self.subTest(case=name):
                self.collection_health.reset_mock()
                self.collection_health.return_value = health
                result = self._check()
                self.assertFalse(result.is_error)  # an unhealthy collection is a result, not an error
                self.assertEqual(result.structured_content, expected)
                self.collection_health.assert_called_once_with(self.aoss_client.return_value)

    def test_never_uses_the_ask_rag_client_or_the_rag_pipeline(self):
        self.collection_health.return_value = _health()
        self._check()
        self.opensearch_client.assert_not_called()
        self.ask.assert_not_called()

    def test_control_plane_failure_is_a_fixed_service_error(self):
        secret = f"AccessDenied for account 123456789012 on {SECRET_ENDPOINT}"
        for exc in (ClientError({"Error": {"Code": "AccessDeniedException", "Message": secret}},
                                "BatchGetCollection"), NoCredentialsError(), SystemExit(secret)):
            with self.subTest(exc=type(exc).__name__):
                self.collection_health.side_effect = exc
                result = self._check()
                self.assertTrue(result.is_error)
                self.assertEqual(result.content[0].text, "Error executing tool health_check: "
                                 "service_unavailable: the knowledge base or model service is unavailable. "
                                 "Try again later.")

    def test_unexpected_failure_is_reported_generically(self):
        self.collection_health.side_effect = RuntimeError(SECRET_ENDPOINT)
        result = self._check()
        self.assertTrue(result.is_error)
        self.assertEqual(result.content[0].text, "Error executing tool health_check")

    def test_output_reveals_no_private_infrastructure(self):
        for name, (health, _expected) in HEALTH_CASES.items():
            with self.subTest(case=name):
                self.collection_health.return_value = health
                result = self._check()
                rendered = json.dumps(result.structured_content) + result.content[0].text
                for secret in ("SECRET", config.OPENSEARCH_COLLECTION, config.AWS_REGION, "aoss", "amazonaws",
                               "endpoint", "novaops-kb", "us-east-1"):
                    self.assertNotIn(secret, rendered)
                self.assertIsNone(re.search(r"\b\d{12}\b", rendered))

    def test_writes_nothing_to_stdout(self):
        self.collection_health.return_value = _health()
        out = io.StringIO()
        with redirect_stdout(out):
            self._check()
        self.assertEqual(out.getvalue(), "")


class HealthCheckRealUseCaseTests(_InfrastructureGuard):
    """Through the real manage.collection_health with a fake control plane — proves
    the tool consumes the existing use case, not a second implementation."""

    def _fake_aoss(self, collection):
        aoss = MagicMock()
        aoss.batch_get_collection.return_value = {"collectionDetails": [collection] if collection else []}
        self.aoss_client.return_value = aoss
        return aoss

    def _check(self):
        return _call(mcp_server.build_server("employee"), lambda c: c.call_tool("health_check", {}))

    def test_active_collection_with_chunks_is_ready(self):
        self._fake_aoss({"id": "abc123", "status": "ACTIVE", "collectionEndpoint": SECRET_ENDPOINT})
        data_plane = MagicMock()
        data_plane.indices.exists.return_value = True
        data_plane.count.return_value = {"count": 400}
        self.opensearch_client.return_value = data_plane  # collection_health's own data-plane client
        result = self._check()
        self.assertEqual(result.structured_content, HEALTH_CASES["healthy"][1])
        self.assertNotIn("SECRET", json.dumps(result.structured_content) + result.content[0].text)

    def test_missing_collection_is_not_ready_and_skips_the_data_plane(self):
        self._fake_aoss(None)
        result = self._check()
        self.assertEqual(result.structured_content, HEALTH_CASES["missing collection"][1])
        self.opensearch_client.assert_not_called()

    def test_control_plane_exception_message_does_not_leak(self):
        aoss = self._fake_aoss(None)
        aoss.batch_get_collection.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": f"denied {SECRET_ENDPOINT}"}}, "BatchGetCollection")
        result = self._check()
        self.assertTrue(result.is_error)
        self.assertIn("service_unavailable", result.content[0].text)
        self.assertNotIn("SECRET", result.content[0].text)


class LazyOpenSearchClientTests(_InfrastructureGuard):
    def test_nothing_is_created_until_first_use_then_reused(self):
        lazy = mcp_server.LazyOpenSearchClient()
        self.opensearch_client.assert_not_called()
        first, second = lazy.get(), lazy.get()
        self.assertIs(first, second)
        self.opensearch_client.assert_called_once_with()

    def test_a_failed_creation_is_not_cached(self):
        sentinel = object()
        self.opensearch_client.side_effect = [SystemExit("Collection 'x' not found"), sentinel]
        lazy = mcp_server.LazyOpenSearchClient()
        with self.assertRaises(SystemExit):
            lazy.get()
        self.assertIs(lazy.get(), sentinel)
        self.assertEqual(self.opensearch_client.call_count, 2)


if __name__ == "__main__":
    unittest.main()
