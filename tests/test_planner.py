"""Deterministic tests for planner.py — no network, no AWS, no real credentials.

The shared `bedrock` object planner.py imports from client.py is patched;
nothing here makes a real Bedrock call.
"""
import os
import unittest
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import client  # noqa: E402
import planner  # noqa: E402


def _tool_response(subjects):
    """A Bedrock Converse response carrying one toolUse block, as the forced
    pick_subjects tool would return it."""
    return {"output": {"message": {"content": [
        {"toolUse": {"name": "pick_subjects", "input": {"subjects": subjects}}}
    ]}}}


class PlanSubjectsTests(unittest.TestCase):
    @patch("planner.bedrock")
    def test_single_subject_plan(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(["pay_and_benefits"])
        self.assertEqual(planner.plan_subjects("How much do I get paid?"), ["pay_and_benefits"])

    @patch("planner.bedrock")
    def test_multiple_subjects_plan(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(
            ["severance_and_termination", "performance_and_feedback"]
        )
        self.assertEqual(
            planner.plan_subjects("severance after underperformance?"),
            ["severance_and_termination", "performance_and_feedback"],
        )

    @patch("planner.bedrock")
    def test_empty_plan_is_returned_as_empty_list(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response([])
        self.assertEqual(planner.plan_subjects("tell me everything"), [])

    @patch("planner.bedrock")
    def test_duplicate_subjects_are_deduplicated(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(
            ["pay_and_benefits", "pay_and_benefits", "time_off_and_leave"]
        )
        self.assertEqual(
            planner.plan_subjects("q"), ["pay_and_benefits", "time_off_and_leave"]
        )

    @patch("planner.bedrock")
    def test_unknown_subjects_are_dropped(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(
            ["pay_and_benefits", "not_a_real_subject"]
        )
        self.assertEqual(planner.plan_subjects("q"), ["pay_and_benefits"])
        self.assertNotIn("not_a_real_subject", planner.SUBJECTS)

    @patch("planner.bedrock")
    def test_no_tooluse_block_returns_empty_list(self, fake_bedrock):
        fake_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "huh?"}]}}}
        self.assertEqual(planner.plan_subjects("q"), [])

    @patch("planner.bedrock")
    def test_bedrock_exception_propagates_instead_of_becoming_empty_plan(self, fake_bedrock):
        fake_bedrock.converse.side_effect = RuntimeError("throttled")
        with self.assertRaises(RuntimeError):
            planner.plan_subjects("q")

    def test_planner_does_not_instantiate_its_own_boto3_client(self):
        self.assertFalse(hasattr(planner, "boto3"))
        # The bedrock object planner uses IS client.py's shared instance, not a
        # second client constructed inside planner.py.
        self.assertIs(planner.bedrock, client.bedrock)

    def test_uses_the_same_subjects_enum_as_the_tagger(self):
        import subjects
        self.assertIs(planner.SUBJECTS, subjects.SUBJECTS)


if __name__ == "__main__":
    unittest.main()
