"""The MCP server's published contract, pinned against a recorded snapshot.

tests/fixtures/mcp_contract_snapshot.json was recorded from the server before the
shared public views moved out of mcp_server.py. Any difference — a tool's
description, input or output schema, the capabilities result, or a projection of
a fixed input — fails here, so a refactor cannot change what MCP clients see
without it being noticed.

To change the contract deliberately, regenerate the snapshot and review the diff:

    python -c "import sys; sys.path.insert(0, 'tests'); import test_mcp_contract as t; t.write_snapshot()"

No subprocess, no network, no AWS: the server runs over the SDK's in-memory client.
"""
import importlib.util
import json
import os
import unittest
from datetime import date
from pathlib import Path

if importlib.util.find_spec("mcp") is None:
    raise unittest.SkipTest("MCP tests need the optional dependency: pip install -r requirements-mcp.txt")

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import anyio  # noqa: E402
from mcp import Client  # noqa: E402

import mcp_server  # noqa: E402
from manage import CollectionHealth  # noqa: E402
from models import (  # noqa: E402
    AskResult,
    Candidate,
    LiveJudgement,
    RetrievalResult,
    SecurityAudit,
    SelectedChunk,
    SelectionResult,
)

SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "mcp_contract_snapshot.json"

_JUDGEMENT = LiveJudgement(
    faithfulness=0.9, faithfulness_reason="grounded in the context",
    context_relevance=0.8, context_relevance_reason="relevant",
    refused=False, completeness=0.7, completeness_reason="mostly complete",
)


def _candidate(source, audience="employee", rank=0, rerank_score=0.9):
    return Candidate(text=f"SENTINEL-CHUNK-TEXT {source}", source=source,
                     corpus="handbook" if audience == "employee" else "manager_playbook",
                     audience=audience, subjects=["time_off_and_leave"], last_updated="2025-03-01",
                     vector_score=0.5, vector_rank=rank, rerank_score=rerank_score)


def _ask_result(status="selected", violation=False, judgement=None):
    pool = [_candidate("pto.md"), _candidate("holidays.md", rank=1, rerank_score=0.6)]
    if violation:
        pool.append(_candidate("severance.md", audience="manager", rank=2))
    chunks = [] if status == "not_found" else [SelectedChunk(candidate=pool[1], final_rank=1),
                                               SelectedChunk(candidate=pool[0], final_rank=0)]
    return AskResult(
        question="How does PTO accrue?", audience="employee", config="filter + rerank dynamic",
        planned_subjects=["time_off_and_leave"],
        retrieval=RetrievalResult(
            audience="employee", subjects_applied=["time_off_and_leave"], top_k_requested=10,
            candidates=pool,
            security=SecurityAudit(violation=violation, violating_sources=["severance.md"] if violation else []),
            cutoff=date(2025, 1, 1)),
        selection=SelectionResult(status=status, chunks=chunks,
                                  context_texts=[c.candidate.text for c in chunks] or ["not found"]),
        answer="SENTINEL generated answer", judgement=judgement,
    )


_ASK_INPUTS = {
    "selected": _ask_result(),
    "selected_judged": _ask_result(judgement=_JUDGEMENT),
    "not_found": _ask_result(status="not_found"),
    "security_violation": _ask_result(violation=True, judgement=_JUDGEMENT),
}

_HEALTH_INPUTS = {
    "ready": CollectionHealth(status="ACTIVE", endpoint="https://SENTINEL-ENDPOINT", index_exists=True,
                              chunk_count=400, data_plane_error=None),
    "empty_index": CollectionHealth(status="ACTIVE", endpoint="https://SENTINEL-ENDPOINT", index_exists=True,
                                    chunk_count=0, data_plane_error=None),
    "no_index": CollectionHealth(status="ACTIVE", endpoint="https://SENTINEL-ENDPOINT", index_exists=False,
                                 chunk_count=None, data_plane_error=None),
    "data_plane_unreachable": CollectionHealth(status="ACTIVE", endpoint="https://SENTINEL-ENDPOINT",
                                               index_exists=None, chunk_count=None,
                                               data_plane_error="SENTINEL connection error"),
    "creating": CollectionHealth(status="CREATING", endpoint=None, index_exists=None, chunk_count=None,
                                 data_plane_error=None),
    "missing": CollectionHealth(status=None, endpoint=None, index_exists=None, chunk_count=None,
                                data_plane_error=None),
}


def _surface(role):
    async def run():
        async with Client(mcp_server.build_server(role)) as c:
            tools = await c.list_tools()
            resources = await c.list_resources()
            capabilities = await c.call_tool("get_rag_capabilities", {})
            return tools, resources, capabilities
    return anyio.run(run)


def current_contract() -> dict:
    """The contract as the current code publishes it, in JSON-comparable form."""
    tools, resources, _ = _surface("employee")
    return {
        "server": {"name": mcp_server.SERVER_NAME, "version": mcp_server.SERVER_VERSION},
        "tools": {t.name: {"description": t.description, "input_schema": t.input_schema,
                           "output_schema": t.output_schema}
                  for t in sorted(tools.tools, key=lambda t: t.name)},
        "resources": [{"uri": str(r.uri), "name": r.name, "description": r.description, "mime_type": r.mime_type}
                      for r in resources.resources],
        "capabilities": {role: _surface(role)[2].structured_content for role in ("employee", "manager")},
        "project_ask_result": {name: mcp_server.project_ask_result(r).model_dump(mode="json")
                               for name, r in _ASK_INPUTS.items()},
        "project_health": {name: mcp_server.project_health(h).model_dump(mode="json")
                           for name, h in _HEALTH_INPUTS.items()},
    }


def write_snapshot() -> None:
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(current_contract(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


class McpContractSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.current = json.loads(json.dumps(current_contract()))  # normalize tuples etc. like the file

    def test_server_identity_is_unchanged(self):
        self.assertEqual(self.current["server"], self.recorded["server"])

    def test_every_tool_description_and_schema_is_unchanged(self):
        self.assertEqual(sorted(self.current["tools"]), sorted(self.recorded["tools"]))
        for name, recorded in self.recorded["tools"].items():
            for part in ("description", "input_schema", "output_schema"):
                with self.subTest(tool=name, part=part):
                    self.assertEqual(self.current["tools"][name][part], recorded[part])

    def test_resources_are_unchanged(self):
        self.assertEqual(self.current["resources"], self.recorded["resources"])

    def test_capabilities_result_is_unchanged_for_every_role(self):
        self.assertEqual(self.current["capabilities"], self.recorded["capabilities"])

    def test_ask_projection_is_unchanged(self):
        for name, recorded in self.recorded["project_ask_result"].items():
            with self.subTest(case=name):
                self.assertEqual(self.current["project_ask_result"][name], recorded)

    def test_health_projection_is_unchanged(self):
        for name, recorded in self.recorded["project_health"].items():
            with self.subTest(case=name):
                self.assertEqual(self.current["project_health"][name], recorded)

    def test_the_server_uses_the_shared_public_views_not_copies(self):
        import public_views
        for name in ("AskRagResult", "HealthResult", "project_ask_result", "project_health", "WITHHELD_ANSWER",
                     "SECURITY_VIOLATION_EXPLANATION", "MAX_QUESTION_CHARS", "ConfigurationCapability"):
            with self.subTest(name=name):
                self.assertIs(getattr(mcp_server, name), getattr(public_views, name))

    def test_the_snapshot_itself_holds_no_protected_content(self):
        rendered = SNAPSHOT.read_text(encoding="utf-8")
        for secret in ("SENTINEL-CHUNK-TEXT", "severance.md", "SENTINEL-ENDPOINT", "SENTINEL connection error",
                       "How does PTO accrue?"):
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
