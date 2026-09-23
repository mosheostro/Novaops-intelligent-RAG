"""Deterministic tests for reranker.py — no network, no AWS, no real credentials.

The shared `bedrock` object reranker.py imports from client.py is patched;
nothing here makes a real Bedrock call.
"""
import os
import unittest
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import client  # noqa: E402
import reranker  # noqa: E402


def _rank_response(scored):
    """A Bedrock Converse response carrying one toolUse block, as the forced
    `rank` tool would return it. `scored`: [(index, score), ...]."""
    return {"output": {"message": {"content": [
        {"toolUse": {"name": "rank", "input": {
            "scores": [{"index": i, "score": s} for i, s in scored]
        }}}
    ]}}}


CANDIDATES = [
    {"text": "chunk zero"},
    {"text": "chunk one"},
    {"text": "chunk two"},
]


class RerankAllTests(unittest.TestCase):
    @patch("reranker.bedrock")
    def test_returns_a_pair_per_candidate_best_first(self, fake_bedrock):
        fake_bedrock.converse.return_value = _rank_response([(0, 0.2), (1, 0.9), (2, 0.5)])
        result = reranker.rerank_all("q", CANDIDATES)
        self.assertEqual(len(result), 3)
        self.assertEqual([c["text"] for c, _ in result],
                          ["chunk one", "chunk two", "chunk zero"])
        self.assertEqual([s for _, s in result], [0.9, 0.5, 0.2])

    @patch("reranker.bedrock")
    def test_one_nova_call_scores_every_candidate(self, fake_bedrock):
        fake_bedrock.converse.return_value = _rank_response([(0, 0.1), (1, 0.2), (2, 0.3)])
        reranker.rerank_all("q", CANDIDATES)
        fake_bedrock.converse.assert_called_once()

    @patch("reranker.bedrock")
    def test_whole_chunk_text_is_sent_not_truncated(self, fake_bedrock):
        long_text = "word " * 2000
        fake_bedrock.converse.return_value = _rank_response([(0, 0.5)])
        reranker.rerank_all("q", [{"text": long_text}])
        _, kwargs = fake_bedrock.converse.call_args
        prompt = kwargs["messages"][0]["content"][0]["text"]
        self.assertIn(long_text.strip(), prompt)

    @patch("reranker.bedrock")
    def test_omitted_candidate_scores_zero(self, fake_bedrock):
        # Only candidate 1 is scored; 0 and 2 are omitted by the model.
        fake_bedrock.converse.return_value = _rank_response([(1, 0.7)])
        result = reranker.rerank_all("q", CANDIDATES)
        by_text = {c["text"]: s for c, s in result}
        self.assertEqual(by_text["chunk one"], 0.7)
        self.assertEqual(by_text["chunk zero"], 0.0)
        self.assertEqual(by_text["chunk two"], 0.0)

    @patch("reranker.bedrock")
    def test_out_of_range_index_is_ignored(self, fake_bedrock):
        fake_bedrock.converse.return_value = _rank_response([(0, 0.5), (99, 0.9), (-1, 0.9)])
        result = reranker.rerank_all("q", CANDIDATES)
        self.assertEqual(len(result), 3)  # no phantom candidate added
        by_text = {c["text"]: s for c, s in result}
        self.assertEqual(by_text["chunk zero"], 0.5)

    @patch("reranker.bedrock")
    def test_malformed_score_entry_is_skipped_not_fatal(self, fake_bedrock):
        resp = {"output": {"message": {"content": [
            {"toolUse": {"name": "rank", "input": {"scores": [
                {"index": 0, "score": "not-a-number"},
                {"index": 1, "score": 0.6},
                {"index": 2},  # missing "score" entirely
            ]}}}
        ]}}}
        fake_bedrock.converse.return_value = resp
        result = reranker.rerank_all("q", CANDIDATES)  # must not raise
        by_text = {c["text"]: s for c, s in result}
        self.assertEqual(by_text["chunk one"], 0.6)
        self.assertEqual(by_text["chunk zero"], 0.0)
        self.assertEqual(by_text["chunk two"], 0.0)

    @patch("reranker.bedrock")
    def test_scores_are_clamped_to_0_1(self, fake_bedrock):
        fake_bedrock.converse.return_value = _rank_response([(0, 5.0), (1, -3.0), (2, 0.4)])
        result = reranker.rerank_all("q", CANDIDATES)
        by_text = {c["text"]: s for c, s in result}
        self.assertEqual(by_text["chunk zero"], 1.0)
        self.assertEqual(by_text["chunk one"], 0.0)
        self.assertEqual(by_text["chunk two"], 0.4)

    @patch("reranker.bedrock")
    def test_ties_keep_original_candidate_order_stable_sort(self, fake_bedrock):
        fake_bedrock.converse.return_value = _rank_response([(0, 0.5), (1, 0.5), (2, 0.5)])
        result = reranker.rerank_all("q", CANDIDATES)
        self.assertEqual([c["text"] for c, _ in result], ["chunk zero", "chunk one", "chunk two"])

    @patch("reranker.bedrock")
    def test_no_tooluse_block_scores_everything_zero(self, fake_bedrock):
        fake_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "??"}]}}}
        result = reranker.rerank_all("q", CANDIDATES)
        self.assertEqual([s for _, s in result], [0.0, 0.0, 0.0])

    @patch("reranker.bedrock")
    def test_bedrock_exception_propagates(self, fake_bedrock):
        fake_bedrock.converse.side_effect = RuntimeError("throttled")
        with self.assertRaises(RuntimeError):
            reranker.rerank_all("q", CANDIDATES)

    def test_reranker_does_not_instantiate_its_own_boto3_client(self):
        self.assertFalse(hasattr(reranker, "boto3"))
        self.assertIs(reranker.bedrock, client.bedrock)


class RerankTests(unittest.TestCase):
    """rerank() is the fixed-count cut on top of rerank_all() -- the reference
    API this module preserves alongside rerank_all()."""

    @patch("reranker.bedrock")
    def test_keeps_exactly_top_k_best_first(self, fake_bedrock):
        fake_bedrock.converse.return_value = _rank_response([(0, 0.2), (1, 0.9), (2, 0.5)])
        result = reranker.rerank("q", CANDIDATES, top_k=2)
        self.assertEqual([c["text"] for c, _ in result], ["chunk one", "chunk two"])

    @patch("reranker.bedrock")
    def test_delegates_to_rerank_all_not_a_second_implementation(self, fake_bedrock):
        fake_bedrock.converse.return_value = _rank_response([(0, 0.1), (1, 0.2), (2, 0.3)])
        reranker.rerank("q", CANDIDATES, top_k=1)
        fake_bedrock.converse.assert_called_once()  # still just one Nova call


if __name__ == "__main__":
    unittest.main()
