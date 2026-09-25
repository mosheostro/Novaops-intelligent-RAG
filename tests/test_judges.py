"""Deterministic tests for judges.py's LLM-based refusal judge — no network,
no AWS, no real credentials. `judges.bedrock` is patched (the shared client
from client.py; judges.py builds no client of its own).

These tests mock the model's response and assert `refusal()` plumbs it through
correctly — they cannot prove the model's real semantic judgment is correct
(that's what the live eval, not a unit test, is for). What they DO prove: the
implementation makes exactly one forced tool call reading the question and the
full answer, and contains no keyword/substring matching of any kind — so a
mocked "true" or "false" from the model is trusted as-is, regardless of what
words the answer happens to contain.
"""
import os
import unittest
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import client  # noqa: E402
import judges  # noqa: E402


def _refusal_response(refused: bool, reason: str = "ok"):
    """A Bedrock Converse response carrying one toolUse block, as the forced
    submit_refusal_judgment tool would return it."""
    return {"output": {"message": {"content": [
        {"toolUse": {"name": "submit_refusal_judgment", "input": {"refused": refused, "reason": reason}}}
    ]}}}


class RefusalJudgeTests(unittest.TestCase):
    @patch("judges.bedrock")
    def test_legitimate_answer_with_a_refusal_like_substring_is_not_a_refusal(self, fake_bedrock):
        # "do not have" appears naturally here -- the old keyword heuristic
        # would have misclassified this as a refusal. The model says it isn't.
        fake_bedrock.converse.return_value = _refusal_response(False)
        answer = ("Quarterly conversations do not have to wait for the formal review "
                  "cycle -- managers are encouraged to give feedback continuously.")
        result = judges.refusal("How often should feedback be given?", answer)
        self.assertFalse(result)

    @patch("judges.bedrock")
    def test_explicit_refusal_is_a_refusal(self, fake_bedrock):
        fake_bedrock.converse.return_value = _refusal_response(True)
        answer = "I don't have enough information in the provided context to answer this question."
        result = judges.refusal("What was the total AWS bill last quarter?", answer)
        self.assertTrue(result)

    @patch("judges.bedrock")
    def test_refusal_without_any_of_the_old_keyword_cues_is_still_detected(self, fake_bedrock):
        # None of the old substring cues ("don't have", "not available", "cannot
        # answer", ...) appear anywhere below -- proving this judges semantics,
        # not keywords. The model (mocked) correctly still says true.
        fake_bedrock.converse.return_value = _refusal_response(True)
        answer = "That's outside what I can help with based on what's in front of me."
        result = judges.refusal("What was the total AWS bill last quarter?", answer)
        self.assertTrue(result)

    @patch("judges.bedrock")
    def test_normal_answer_is_not_a_refusal(self, fake_bedrock):
        fake_bedrock.converse.return_value = _refusal_response(False)
        answer = "You get 20 days of vacation per year, plus 11 local holidays."
        result = judges.refusal("How many vacation days do I get?", answer)
        self.assertFalse(result)

    @patch("judges.bedrock")
    def test_uses_a_forced_tool_call_not_free_text_parsing(self, fake_bedrock):
        fake_bedrock.converse.return_value = _refusal_response(False)
        judges.refusal("q", "a")
        _, kwargs = fake_bedrock.converse.call_args
        self.assertEqual(kwargs["toolConfig"]["toolChoice"], {"tool": {"name": "submit_refusal_judgment"}})
        tool_names = [t["toolSpec"]["name"] for t in kwargs["toolConfig"]["tools"]]
        self.assertEqual(tool_names, ["submit_refusal_judgment"])

    @patch("judges.bedrock")
    def test_passes_both_question_and_answer_to_the_model(self, fake_bedrock):
        fake_bedrock.converse.return_value = _refusal_response(False)
        judges.refusal("What is the vacation policy?", "You get 20 days per year.")
        _, kwargs = fake_bedrock.converse.call_args
        prompt = kwargs["messages"][0]["content"][0]["text"]
        self.assertIn("What is the vacation policy?", prompt)
        self.assertIn("You get 20 days per year.", prompt)

    @patch("judges.bedrock")
    def test_uses_the_configured_model_and_zero_temperature(self, fake_bedrock):
        fake_bedrock.converse.return_value = _refusal_response(False)
        judges.refusal("q", "a")
        _, kwargs = fake_bedrock.converse.call_args
        self.assertEqual(kwargs["modelId"], judges.MODEL_ID)
        self.assertEqual(kwargs["inferenceConfig"]["temperature"], 0.0)

    @patch("judges.bedrock")
    def test_no_tooluse_block_defaults_to_not_refused(self, fake_bedrock):
        fake_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "unparseable"}]}}}
        self.assertFalse(judges.refusal("q", "a"))

    def test_uses_the_shared_client_no_client_of_its_own(self):
        self.assertFalse(hasattr(judges, "boto3"))
        self.assertIs(judges.bedrock, client.bedrock)

    def test_old_keyword_heuristic_is_gone(self):
        self.assertFalse(hasattr(judges, "refused"))


if __name__ == "__main__":
    unittest.main()
