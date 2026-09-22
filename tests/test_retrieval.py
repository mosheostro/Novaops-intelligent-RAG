"""Deterministic tests for retrieval.py — no network, no AWS, no real credentials.

OpenSearch and Bedrock are stubbed with tiny fakes; embed_text is monkeypatched.
Nothing here talks to the live collection or calls a model.
"""
import os
import unittest
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import retrieval  # noqa: E402


class AccessFilterTests(unittest.TestCase):
    def test_employee_is_restricted_to_audience_all(self):
        self.assertEqual(retrieval.access_filter("employee"), [{"term": {"audience": "all"}}])

    def test_manager_has_no_restriction(self):
        self.assertEqual(retrieval.access_filter("manager"), [])

    def test_unknown_audience_is_rejected_not_treated_as_manager(self):
        # The security bug this hardens: an unrecognized role must never fall
        # through to the "no restriction" branch.
        with self.assertRaises(Exception):
            retrieval.access_filter("marketing")

    def test_empty_audience_is_rejected(self):
        with self.assertRaises(Exception):
            retrieval.access_filter("")

    def test_arbitrary_unsupported_role_is_rejected(self):
        for role in ("HR", "admin", "guest", "Employee", "MANAGER"):
            with self.subTest(role=role):
                with self.assertRaises(Exception):
                    retrieval.access_filter(role)

    def test_supported_audiences_is_the_single_source_of_truth(self):
        self.assertEqual(retrieval.SUPPORTED_AUDIENCES, frozenset({"employee", "manager"}))
        for role in retrieval.SUPPORTED_AUDIENCES:
            retrieval.access_filter(role)  # must not raise


class SubjectTermsTests(unittest.TestCase):
    def test_none_means_no_clause(self):
        self.assertEqual(retrieval.subject_terms(None), [])

    def test_empty_list_means_no_clause(self):
        self.assertEqual(retrieval.subject_terms([]), [])

    def test_subjects_produce_a_terms_clause(self):
        self.assertEqual(
            retrieval.subject_terms(["pay_and_benefits", "time_off_and_leave"]),
            [{"terms": {"subjects": ["pay_and_benefits", "time_off_and_leave"]}}],
        )


class RecencyRangeTests(unittest.TestCase):
    def test_none_means_no_clause(self):
        self.assertEqual(retrieval.recency_range(None), [])

    def test_date_produces_a_gte_range_clause(self):
        self.assertEqual(
            retrieval.recency_range("2024-01-01"),
            [{"range": {"last_updated": {"gte": "2024-01-01"}}}],
        )


class BuildFilterTests(unittest.TestCase):
    def test_employee_no_soft_filters_is_access_only(self):
        self.assertEqual(
            retrieval.build_filter("employee"),
            {"bool": {"must": [{"term": {"audience": "all"}}]}},
        )

    def test_manager_no_soft_filters_returns_none(self):
        # No clause is active at all -> None, not an empty bool/must (which would
        # match everything anyway, but None is the explicit "unfiltered" signal).
        self.assertIsNone(retrieval.build_filter("manager"))

    def test_manager_with_subjects_has_only_the_subject_clause(self):
        self.assertEqual(
            retrieval.build_filter("manager", subjects=["hiring_and_onboarding"]),
            {"bool": {"must": [{"terms": {"subjects": ["hiring_and_onboarding"]}}]}},
        )

    def test_empty_subject_list_drops_the_subject_clause_entirely(self):
        # Fail-open: subjects=[] must behave exactly like subjects=None.
        self.assertEqual(
            retrieval.build_filter("employee", subjects=[]),
            {"bool": {"must": [{"term": {"audience": "all"}}]}},
        )

    def test_all_three_clauses_combine_in_one_bool_must(self):
        result = retrieval.build_filter(
            "employee", subjects=["pay_and_benefits"], updated_after="2024-01-01"
        )
        self.assertEqual(result, {"bool": {"must": [
            {"term": {"audience": "all"}},
            {"terms": {"subjects": ["pay_and_benefits"]}},
            {"range": {"last_updated": {"gte": "2024-01-01"}}},
        ]}})

    def test_access_alone_never_disappears_for_employee(self):
        # Regardless of the soft filters, an employee filter always contains the
        # access clause -- the security invariant must survive filter composition.
        for subjects, after in [(None, None), (["x"], None), (None, "2024-01-01"), (["x"], "2024-01-01")]:
            with self.subTest(subjects=subjects, after=after):
                result = retrieval.build_filter("employee", subjects=subjects, updated_after=after)
                self.assertIn({"term": {"audience": "all"}}, result["bool"]["must"])

    def test_unknown_audience_is_rejected_even_with_soft_filters(self):
        # build_filter calls access_filter first, so an unsupported role must be
        # rejected before subjects/recency are even considered.
        with self.assertRaises(Exception):
            retrieval.build_filter("marketing", subjects=["pay_and_benefits"])


class FakeOpenSearchClient:
    """Records the body of the last search()/count() call; returns canned results."""

    def __init__(self, hits=None, count=0):
        self._hits = hits or []
        self._count = count
        self.last_search_body = None
        self.last_search_index = None
        self.last_count_body = None

    def search(self, index, body):
        self.last_search_index = index
        self.last_search_body = body
        return {"hits": {"hits": self._hits}}

    def count(self, index, body):
        self.last_count_body = body
        return {"count": self._count}


SAMPLE_HIT = {
    "_score": 0.9,
    "_source": {
        "text": "chunk text", "source": "severance.md", "corpus": "handbook",
        "audience": "all", "subjects": ["severance_and_termination"], "last_updated": "2024-01-29",
    },
}


class KnnSearchTests(unittest.TestCase):
    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_filter_is_placed_inside_the_knn_block_not_as_post_filter(self, _embed):
        client = FakeOpenSearchClient(hits=[SAMPLE_HIT])
        retrieval.knn_search(client, "how much severance?", audience="employee", top_k=4)
        body = client.last_search_body
        self.assertIn("filter", body["query"]["knn"]["vector"])
        self.assertEqual(
            body["query"]["knn"]["vector"]["filter"],
            {"bool": {"must": [{"term": {"audience": "all"}}]}},
        )
        self.assertNotIn("post_filter", body)

    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_unfiltered_search_omits_the_filter_key_entirely(self, _embed):
        client = FakeOpenSearchClient()
        retrieval.knn_search(client, "q", audience="manager", top_k=10)
        self.assertNotIn("filter", client.last_search_body["query"]["knn"]["vector"])

    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_top_k_controls_both_size_and_k(self, _embed):
        client = FakeOpenSearchClient()
        retrieval.knn_search(client, "q", audience="manager", top_k=10)
        body = client.last_search_body
        self.assertEqual(body["size"], 10)
        self.assertEqual(body["query"]["knn"]["vector"]["k"], 10)

        client2 = FakeOpenSearchClient()
        retrieval.knn_search(client2, "q", audience="manager", top_k=4)
        self.assertEqual(client2.last_search_body["size"], 4)
        self.assertEqual(client2.last_search_body["query"]["knn"]["vector"]["k"], 4)

    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_source_requests_all_metadata_needed_downstream(self, _embed):
        client = FakeOpenSearchClient()
        retrieval.knn_search(client, "q", audience="employee", top_k=4)
        requested = set(client.last_search_body["_source"])
        self.assertEqual(
            requested,
            {"text", "source", "corpus", "audience", "subjects", "last_updated"},
        )

    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_returns_full_hits_not_just_text(self, _embed):
        client = FakeOpenSearchClient(hits=[SAMPLE_HIT])
        hits = retrieval.knn_search(client, "q", audience="employee", top_k=4)
        self.assertEqual(hits, [SAMPLE_HIT])
        self.assertIn("audience", hits[0]["_source"])

    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_embeds_the_query_text(self, embed):
        client = FakeOpenSearchClient()
        retrieval.knn_search(client, "how much severance?", audience="manager", top_k=4)
        embed.assert_called_once_with("how much severance?")

    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_indexes_against_the_shared_index_name(self, _embed):
        client = FakeOpenSearchClient()
        retrieval.knn_search(client, "q", audience="manager", top_k=4)
        self.assertEqual(client.last_search_index, retrieval.INDEX_NAME)

    @patch("retrieval.embed_text", return_value=[0.1, 0.2, 0.3])
    def test_unsupported_audience_never_reaches_opensearch(self, embed):
        # The request must be rejected before any client call -- not sent with a
        # filter that happens to match nothing.
        client = FakeOpenSearchClient(hits=[SAMPLE_HIT])
        with self.assertRaises(Exception):
            retrieval.knn_search(client, "q", audience="marketing", top_k=4)
        self.assertIsNone(client.last_search_body)
        embed.assert_not_called()


class CountCandidatesTests(unittest.TestCase):
    def test_no_filters_uses_match_all(self):
        client = FakeOpenSearchClient(count=400)
        n = retrieval.count_candidates(client, audience="manager")
        self.assertEqual(n, 400)
        self.assertEqual(client.last_count_body["query"], {"match_all": {}})

    def test_uses_the_same_build_filter_as_knn_search(self):
        client = FakeOpenSearchClient(count=217)
        retrieval.count_candidates(client, audience="employee")
        self.assertEqual(
            client.last_count_body["query"],
            retrieval.build_filter("employee"),
        )

    def test_soft_filter_narrows_relative_to_access_only(self):
        # Not a live assertion about the index -- just that count_candidates wires
        # the extra clause through to the query it sends.
        client = FakeOpenSearchClient(count=65)
        retrieval.count_candidates(client, audience="employee", subjects=["pay_and_benefits"])
        query = client.last_count_body["query"]
        self.assertIn({"terms": {"subjects": ["pay_and_benefits"]}}, query["bool"]["must"])

    def test_unsupported_audience_never_reaches_opensearch(self):
        client = FakeOpenSearchClient(count=400)
        with self.assertRaises(Exception):
            retrieval.count_candidates(client, audience="marketing")
        self.assertIsNone(client.last_count_body)


class AnswerTests(unittest.TestCase):
    def _fake_bedrock_response(self, text="the answer"):
        return {"output": {"message": {"content": [{"text": text}]}}}

    @patch("retrieval.bedrock")
    def test_uses_temperature_0_2_and_maxtokens_1000(self, fake_bedrock):
        fake_bedrock.converse.return_value = self._fake_bedrock_response()
        retrieval.answer("q?", ["ctx1", "ctx2"])
        _, kwargs = fake_bedrock.converse.call_args
        self.assertEqual(kwargs["inferenceConfig"]["temperature"], 0.2)
        self.assertEqual(kwargs["inferenceConfig"]["maxTokens"], 1000)

    @patch("retrieval.bedrock")
    def test_system_prompt_forbids_outside_knowledge_and_guessing(self, fake_bedrock):
        fake_bedrock.converse.return_value = self._fake_bedrock_response()
        retrieval.answer("q?", ["ctx1"])
        _, kwargs = fake_bedrock.converse.call_args
        system_text = kwargs["system"][0]["text"].lower()
        for phrase in ("only", "context"):
            self.assertIn(phrase, system_text)

    @patch("retrieval.bedrock")
    def test_prompt_tells_the_model_contexts_are_relevance_ordered(self, fake_bedrock):
        fake_bedrock.converse.return_value = self._fake_bedrock_response()
        retrieval.answer("q?", ["most relevant chunk", "less relevant chunk"])
        _, kwargs = fake_bedrock.converse.call_args
        user_text = kwargs["messages"][0]["content"][0]["text"]
        self.assertIn("most relevant chunk", user_text)
        self.assertIn("less relevant chunk", user_text)
        self.assertIn("relevan", kwargs["messages"][0]["content"][0]["text"].lower())

    @patch("retrieval.bedrock")
    def test_returns_the_model_text(self, fake_bedrock):
        fake_bedrock.converse.return_value = self._fake_bedrock_response("severance is 8 weeks")
        result = retrieval.answer("q?", ["ctx"])
        self.assertEqual(result, "severance is 8 weeks")

    @patch("retrieval.bedrock")
    def test_uses_the_configured_model_id(self, fake_bedrock):
        fake_bedrock.converse.return_value = self._fake_bedrock_response()
        retrieval.answer("q?", ["ctx"])
        _, kwargs = fake_bedrock.converse.call_args
        self.assertEqual(kwargs["modelId"], retrieval.MODEL_ID)


if __name__ == "__main__":
    unittest.main()
