"""Deterministic tests for ask.py — the single-question pipeline the UI calls.
No network, no AWS, no real credentials.

ask.py reuses eval.py's helpers, so model/network calls are patched where the
two modules imported them: knn_search / plan_subjects / answer / judges on
`ask.<name>`, and rerank_all on `eval.rerank_all` (eval's rerank_candidates
adapter is the one that calls it).
"""
import os
import unittest
from datetime import date
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import ask  # noqa: E402
import models  # noqa: E402
from retrieval import UnsupportedAudienceError  # noqa: E402

CLIENT = object()


def _hit(text, score, audience="all", source="doc.md"):
    return {"_score": score, "_source": {
        "text": text, "source": source, "corpus": "handbook",
        "audience": audience, "subjects": [], "last_updated": "2024-01-01",
    }}


HITS = [_hit(f"chunk {i}", 0.9 - i * 0.05, source=f"d{i}.md") for i in range(10)]


def _rerank_scores(scores):
    """Fake rerank_all: returns the dicts it was given, best first, with `scores`
    assigned in input order."""
    def fake(query, candidates):
        pairs = list(zip(candidates, scores))
        return sorted(pairs, key=lambda p: p[1], reverse=True)
    return fake


class AskPipelineTests(unittest.TestCase):
    def setUp(self):
        self.knn = patch("ask.knn_search", side_effect=lambda c, q, role, subjects, top_k, updated_after=None: HITS[:top_k]).start()
        self.plan = patch("ask.plan_subjects", return_value=["benefits"]).start()
        self.rerank = patch("eval.rerank_all", side_effect=_rerank_scores(
            [0.9, 0.2, 0.7, 0.1, 0.65, 0.0, 0.0, 0.0, 0.0, 0.0])).start()
        self.answer = patch("ask.answer", return_value="the answer").start()
        self.faith = patch("ask.faithfulness", return_value=(0.8, "grounded")).start()
        self.relevance = patch("ask.context_relevance", return_value=(0.6, "mostly relevant")).start()
        self.refusal = patch("ask.refusal", return_value=False).start()
        self.completeness = patch("judges.completeness").start()
        self.context_completeness = patch("ask.context_completeness", return_value=(0.7, "covers most")).start()
        self.addCleanup(patch.stopall)

    def test_baseline_is_plain_vector_top4_without_planner_or_rerank(self):
        r = ask.ask(CLIENT, "q?", "employee", "baseline")
        self.plan.assert_not_called()
        self.rerank.assert_not_called()
        self.knn.assert_called_once_with(CLIENT, "q?", "employee", subjects=None, top_k=4, updated_after=None)
        self.assertIsNone(r.planned_subjects)
        self.assertEqual(r.retrieval.subjects_applied, None)
        self.assertEqual(len(r.selection.chunks), 4)
        self.assertEqual(r.answer, "the answer")

    def test_filter_only_plans_once_and_filters_by_subjects(self):
        r = ask.ask(CLIENT, "q?", "employee", "filter-only")
        self.plan.assert_called_once_with("q?")
        self.rerank.assert_not_called()
        self.knn.assert_called_once_with(CLIENT, "q?", "employee", subjects=["benefits"], top_k=4, updated_after=None)
        self.assertEqual(r.planned_subjects, ["benefits"])
        self.assertEqual(r.retrieval.subjects_applied, ["benefits"])

    def test_rerank_only_uses_pool_of_10_and_static_top3(self):
        r = ask.ask(CLIENT, "q?", "manager", "rerank-only")
        self.plan.assert_not_called()
        self.knn.assert_called_once_with(CLIENT, "q?", "manager", subjects=None, top_k=10, updated_after=None)
        self.rerank.assert_called_once()
        self.assertEqual([c.candidate.text for c in r.selection.chunks], ["chunk 0", "chunk 2", "chunk 4"])
        self.assertEqual(len(r.retrieval.candidates), 10)

    def test_filter_rerank_static_plans_and_reranks(self):
        r = ask.ask(CLIENT, "q?", "employee", "filter + rerank static")
        self.plan.assert_called_once()
        self.rerank.assert_called_once()
        self.knn.assert_called_once_with(CLIENT, "q?", "employee", subjects=["benefits"], top_k=10, updated_after=None)
        self.assertEqual(len(r.selection.chunks), 3)

    def test_filter_rerank_dynamic_keeps_only_scores_at_or_above_threshold(self):
        r = ask.ask(CLIENT, "q?", "employee", "filter + rerank dynamic")
        self.assertEqual([c.candidate.text for c in r.selection.chunks], ["chunk 0", "chunk 2", "chunk 4"])

    def test_dynamic_with_nothing_above_threshold_is_not_found_and_answers_from_sentinel(self):
        self.rerank.side_effect = _rerank_scores([0.1] * 10)
        r = ask.ask(CLIENT, "q?", "employee", "filter + rerank dynamic")
        self.assertEqual(r.selection.status, "not_found")
        self.answer.assert_called_once_with("q?", ["not found"])

    def test_judges_are_skipped_by_default(self):
        r = ask.ask(CLIENT, "q?", "employee", "baseline")
        self.faith.assert_not_called()
        self.relevance.assert_not_called()
        self.refusal.assert_not_called()
        self.assertIsNone(r.judgement)

    def test_judge_true_runs_content_judges_and_refusal_detection_but_not_completeness(self):
        r = ask.ask(CLIENT, "q?", "employee", "baseline", judge=True)
        contexts = [h["_source"]["text"] for h in HITS[:4]]
        self.faith.assert_called_once_with("q?", contexts, "the answer")
        self.relevance.assert_called_once_with("q?", contexts)
        self.refusal.assert_called_once_with("q?", "the answer")  # the same judge batch evaluation uses
        self.completeness.assert_not_called()                     # batch judge needs key_facts; never used here
        self.context_completeness.assert_called_once_with("q?", contexts, "the answer")
        self.assertEqual(r.judgement, models.LiveJudgement(
            faithfulness=0.8, faithfulness_reason="grounded",
            context_relevance=0.6, context_relevance_reason="mostly relevant",
            refused=False, completeness=0.7, completeness_reason="covers most",
        ))

    def test_refusal_skips_context_completeness_without_a_bedrock_call(self):
        self.refusal.return_value = True
        r = ask.ask(CLIENT, "q?", "employee", "baseline", judge=True)
        self.context_completeness.assert_not_called()
        self.assertIsNone(r.judgement.completeness)
        self.assertIsNone(r.judgement.completeness_reason)

    def test_no_selected_chunks_skips_context_completeness(self):
        self.rerank.side_effect = _rerank_scores([0.1] * 10)  # dynamic cut keeps nothing -> not_found
        r = ask.ask(CLIENT, "q?", "employee", "filter + rerank dynamic", judge=True)
        self.assertEqual(r.selection.status, "not_found")
        self.context_completeness.assert_not_called()
        self.assertIsNone(r.judgement.completeness)

    def test_judges_off_runs_no_completeness_either(self):
        ask.ask(CLIENT, "q?", "employee", "baseline")
        self.context_completeness.assert_not_called()

    def test_detected_refusal_is_reported_as_refused(self):
        self.answer.return_value = "I don't have that information."
        self.refusal.return_value = True
        r = ask.ask(CLIENT, "q?", "employee", "baseline", judge=True)
        self.assertTrue(r.judgement.refused)
        self.assertFalse(hasattr(r.judgement, "refusal_ok"))       # no expectation -> no Refusal OK

    def test_unsupported_role_raises_before_any_model_or_search_call(self):
        with self.assertRaises(UnsupportedAudienceError):
            ask.ask(CLIENT, "q?", "admin", "filter + rerank dynamic")
        self.plan.assert_not_called()
        self.knn.assert_not_called()
        self.answer.assert_not_called()

    def test_unknown_config_raises(self):
        with self.assertRaises(ValueError):
            ask.ask(CLIENT, "q?", "employee", "nope")

    def test_security_audit_flags_manager_chunk_returned_to_employee(self):
        self.knn.side_effect = lambda c, q, role, subjects, top_k, updated_after=None: [_hit("leak", 0.9, audience="manager", source="m.md")]
        r = ask.ask(CLIENT, "q?", "employee", "baseline")
        self.assertTrue(r.retrieval.security.violation)
        self.assertEqual(r.retrieval.security.violating_sources, ["m.md"])

    def test_result_echoes_inputs_and_is_frozen(self):
        r = ask.ask(CLIENT, "q?", "manager", "baseline")
        self.assertEqual((r.question, r.audience, r.config), ("q?", "manager", "baseline"))
        with self.assertRaises(Exception):
            r.answer = "changed"


def _dated_hit(text, last_updated, audience="all"):
    return {"_score": 0.9, "_source": {
        "text": text, "source": f"{text}.md", "corpus": "handbook",
        "audience": audience, "subjects": [], "last_updated": last_updated,
    }}


DATED_HITS = [_dated_hit("old", "2023-12-31"), _dated_hit("same-day", "2024-01-01"), _dated_hit("new", "2024-06-01")]


def _fake_store_knn(c, q, role, subjects, top_k, updated_after=None):
    """Stands in for OpenSearch honoring the recency clause retrieval.recency_range
    builds: {"range": {"last_updated": {"gte": cutoff}}} — inclusive."""
    hits = [h for h in DATED_HITS if updated_after is None or h["_source"]["last_updated"] >= updated_after]
    return hits[:top_k]


class AskCutoffTests(unittest.TestCase):
    """The recency cutoff: one date, `last_updated >= cutoff`, independent of the
    configuration and never a replacement for the mandatory access filter."""

    def setUp(self):
        self.knn = patch("ask.knn_search", side_effect=_fake_store_knn).start()
        self.plan = patch("ask.plan_subjects", return_value=["benefits"]).start()
        patch("eval.rerank_all", side_effect=_rerank_scores([0.9] * 10)).start()
        patch("ask.answer", return_value="the answer").start()
        self.addCleanup(patch.stopall)

    def _texts(self, result):
        return [c.text for c in result.retrieval.candidates]

    def test_no_cutoff_passes_no_recency_constraint(self):
        r = ask.ask(CLIENT, "q?", "employee", "baseline")
        self.assertIsNone(self.knn.call_args.kwargs["updated_after"])
        self.assertIsNone(r.retrieval.cutoff)
        self.assertEqual(self._texts(r), ["old", "same-day", "new"])

    def test_cutoff_excludes_older_and_includes_the_cutoff_date_itself(self):
        r = ask.ask(CLIENT, "q?", "employee", "baseline", cutoff=date(2024, 1, 1))
        self.assertEqual(self.knn.call_args.kwargs["updated_after"], "2024-01-01")
        self.assertEqual(self._texts(r), ["same-day", "new"])
        self.assertEqual(r.retrieval.cutoff, date(2024, 1, 1))

    def test_cutoff_is_applied_the_same_way_in_every_configuration(self):
        for config in models.CONFIG_NAMES:
            with self.subTest(config=config):
                self.knn.reset_mock()
                ask.ask(CLIENT, "q?", "employee", config, cutoff=date(2024, 1, 1))
                self.assertEqual(self.knn.call_args.kwargs["updated_after"], "2024-01-01")
                self.assertEqual(self.knn.call_args.args[2], "employee")  # role still passed: access stays mandatory

    def test_unsupported_audience_still_fails_closed_with_a_cutoff(self):
        with self.assertRaises(UnsupportedAudienceError):
            ask.ask(CLIENT, "q?", "admin", "baseline", cutoff=date(2024, 1, 1))
        self.knn.assert_not_called()


class RetrievalResultCutoffFieldTests(unittest.TestCase):
    def test_cutoff_defaults_to_none_so_runs_saved_before_it_existed_still_load(self):
        saved = ('{"audience": "employee", "subjects_applied": null, "top_k_requested": 4, "candidates": [], '
                 '"security": {"violation": false, "violating_sources": []}}')
        self.assertIsNone(models.RetrievalResult.model_validate_json(saved).cutoff)

    def test_cutoff_round_trips_as_an_iso_date(self):
        r = models.RetrievalResult(
            audience="employee", subjects_applied=None, top_k_requested=4, candidates=[],
            security=models.SecurityAudit(violation=False, violating_sources=[]), cutoff=date(2024, 1, 1),
        )
        self.assertIn('"cutoff":"2024-01-01"', r.model_dump_json())
        self.assertEqual(models.RetrievalResult.model_validate_json(r.model_dump_json()), r)


class RecencyAndAccessCompositionTests(unittest.TestCase):
    """The filter ask.py ultimately sends: a cutoff adds a clause, it never
    replaces or removes the employee access clause."""

    def test_employee_filter_with_cutoff_keeps_access_clause_and_inclusive_range(self):
        from retrieval import build_filter
        self.assertEqual(build_filter("employee", updated_after="2024-01-01"), {"bool": {"must": [
            {"term": {"audience": "all"}},
            {"range": {"last_updated": {"gte": "2024-01-01"}}},
        ]}})


if __name__ == "__main__":
    unittest.main()
