"""Deterministic tests for subjects.py — no network, no AWS, no real credentials.

The shared `bedrock` object subjects.py imports from client.py is patched; the
JSON cache file is redirected to a temp path so the real subjects.json is never
touched. Nothing here makes a real Bedrock call or retags the corpus.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import client  # noqa: E402
import subjects  # noqa: E402


def _tool_response(picked):
    """A Bedrock Converse response carrying one toolUse block, as the forced
    tag_subjects tool would return it."""
    return {"output": {"message": {"content": [
        {"toolUse": {"name": "tag_subjects", "input": {"subjects": picked}}}
    ]}}}


class TagArticleTests(unittest.TestCase):
    @patch("subjects.bedrock")
    def test_uses_the_shared_bedrock_client(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(["pay_and_benefits"])
        subjects.tag_article("some article text")
        fake_bedrock.converse.assert_called_once()
        _, kwargs = fake_bedrock.converse.call_args
        self.assertEqual(kwargs["modelId"], subjects.MODEL_ID)

    def test_subjects_module_has_no_boto3_client_of_its_own(self):
        self.assertFalse(hasattr(subjects, "boto3"))
        self.assertIs(subjects.bedrock, client.bedrock)

    @patch("subjects.bedrock")
    def test_returned_subjects_are_filtered_against_the_enum(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(
            ["pay_and_benefits", "not_a_real_subject"]
        )
        self.assertEqual(subjects.tag_article("text"), ["pay_and_benefits"])

    @patch("subjects.bedrock")
    def test_duplicates_are_removed(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(
            ["pay_and_benefits", "pay_and_benefits", "time_off_and_leave"]
        )
        self.assertEqual(subjects.tag_article("text"), ["pay_and_benefits", "time_off_and_leave"])

    @patch("subjects.bedrock")
    def test_no_tooluse_block_returns_empty_list(self, fake_bedrock):
        fake_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "?"}]}}}
        self.assertEqual(subjects.tag_article("text"), [])

    @patch("subjects.bedrock")
    def test_bedrock_exception_propagates_not_a_fake_success(self, fake_bedrock):
        fake_bedrock.converse.side_effect = RuntimeError("throttled")
        with self.assertRaises(RuntimeError):
            subjects.tag_article("text")


class LoadOrTagCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_file = Path(self._tmp.name) / "subjects.json"
        self._patcher = patch.object(subjects, "CACHE_FILE", self.cache_file)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    @patch("subjects.bedrock")
    def test_missing_cache_tags_and_writes_a_new_file(self, fake_bedrock):
        fake_bedrock.converse.return_value = _tool_response(["pay_and_benefits"])
        result = subjects.load_or_tag({"handbook/x.md": "some text"})
        self.assertEqual(result, {"handbook/x.md": ["pay_and_benefits"]})
        self.assertTrue(self.cache_file.exists())
        self.assertEqual(json.loads(self.cache_file.read_text()), result)

    @patch("subjects.bedrock")
    def test_cached_key_is_not_retagged(self, fake_bedrock):
        self.cache_file.write_text(json.dumps({"handbook/x.md": ["pay_and_benefits"]}), encoding="utf-8")
        result = subjects.load_or_tag({"handbook/x.md": "some text"})
        fake_bedrock.converse.assert_not_called()
        self.assertEqual(result, {"handbook/x.md": ["pay_and_benefits"]})

    @patch("subjects.bedrock")
    def test_only_the_missing_key_is_tagged_in_a_mixed_cache(self, fake_bedrock):
        self.cache_file.write_text(json.dumps({"handbook/x.md": ["pay_and_benefits"]}), encoding="utf-8")
        fake_bedrock.converse.return_value = _tool_response(["hiring_and_onboarding"])
        result = subjects.load_or_tag({
            "handbook/x.md": "cached already",
            "handbook/y.md": "new document",
        })
        fake_bedrock.converse.assert_called_once()
        self.assertEqual(result["handbook/x.md"], ["pay_and_benefits"])
        self.assertEqual(result["handbook/y.md"], ["hiring_and_onboarding"])
        self.assertEqual(json.loads(self.cache_file.read_text()), result)


if __name__ == "__main__":
    unittest.main()
