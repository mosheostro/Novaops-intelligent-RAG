"""Deterministic tests for eval.py — no network, no AWS, no real credentials.

knn_search, rerank_all, plan_subjects, answer and the judges are all patched
where eval.py imported them (`eval.<name>`), so no test ever reaches Bedrock or
OpenSearch. A bare object() stands in for the OpenSearch client throughout,
since eval.py never calls anything on it directly — only knn_search (mocked)
receives it.
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

import eval as ev  # noqa: E402  (module name "eval" shadows the builtin only inside this test file)

CLIENT = object()  # eval.py must never call anything on this directly


def _hit(text, score, audience="all", subjects=None, source="doc.md",
         corpus="handbook", last_updated="2024-01-01"):
    return {"_score": score, "_source": {
        "text": text, "source": source, "corpus": corpus,
        "audience": audience, "subjects": subjects or [], "last_updated": last_updated,
    }}


def _q(id="Q1", question="how much severance do I get?", audience="employee",
       expect_refusal=False, key_facts=None):
    return {"id": id, "question": question, "audience": audience,
            "expect_refusal": expect_refusal, "key_facts": key_facts or ["fact one"]}


# ---------------------------------------------------------------------------
# Pure helpers — no mocking needed at all.
# ---------------------------------------------------------------------------

class HitsToCandidatesTests(unittest.TestCase):
    def test_preserves_all_metadata_and_zero_based_vector_rank(self):
        hits = [_hit("a", 0.9), _hit("b", 0.8, audience="manager", subjects=["x"])]
        candidates = ev.hits_to_candidates(hits)
        self.assertEqual(candidates[0]["vector_rank"], 0)
        self.assertEqual(candidates[1]["vector_rank"], 1)
        self.assertEqual(candidates[0]["vector_score"], 0.9)
        self.assertEqual(candidates[1]["audience"], "manager")
        self.assertEqual(candidates[1]["subjects"], ["x"])
        self.assertIsNone(candidates[0]["rerank_score"])


class AnnotateRerankScoresTests(unittest.TestCase):
    def test_attaches_score_by_identity_without_copying(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8)])
        ranked = [(candidates[1], 0.7), (candidates[0], 0.3)]
        ev.annotate_rerank_scores(candidates, ranked)
        self.assertEqual(candidates[0]["rerank_score"], 0.3)
        self.assertEqual(candidates[1]["rerank_score"], 0.7)


class SelectContextTests(unittest.TestCase):
    def _ranked(self, scores):
        candidates = ev.hits_to_candidates([_hit(f"c{i}", 1.0 - i * 0.01) for i in range(len(scores))])
        return list(zip(candidates, scores))

    def test_static_keeps_exactly_top_k_best_first(self):
        ranked = self._ranked([0.95, 0.85, 0.75, 0.65, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0])
        selected, texts = ev.select_context(ranked, "static", static_k=ev.RERANK_STATIC_TOP_K)
        self.assertEqual(len(selected), 3)
        self.assertEqual(texts, ["c0", "c1", "c2"])

    def test_dynamic_keeps_every_score_at_or_above_threshold(self):
        # 4 of 10 candidates clear 0.6 -- dynamic must keep all 4, not static's 3.
        ranked = self._ranked([0.95, 0.85, 0.75, 0.65, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0])
        selected, texts = ev.select_context(ranked, "dynamic", min_score=ev.MIN_RERANK_SCORE)
        self.assertEqual(len(selected), 4)
        self.assertEqual(texts, ["c0", "c1", "c2", "c3"])

    def test_dynamic_returns_not_found_sentinel_when_nothing_clears_the_bar(self):
        ranked = self._ranked([0.3, 0.2, 0.1])
        selected, texts = ev.select_context(ranked, "dynamic", min_score=ev.MIN_RERANK_SCORE)
        self.assertEqual(selected, [])  # NOT a top-1 fallback
        self.assertEqual(texts, ["not found"])

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            ev.select_context(self._ranked([0.5]), "bogus")


class AudienceViolationTests(unittest.TestCase):
    def test_manager_role_is_never_flagged(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9, audience="manager")])
        violation, sources = ev.audience_violation(candidates, "manager")
        self.assertFalse(violation)
        self.assertEqual(sources, [])

    def test_employee_with_only_all_audience_is_clean(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9, audience="all")])
        violation, _ = ev.audience_violation(candidates, "employee")
        self.assertFalse(violation)

    def test_employee_with_a_manager_chunk_is_flagged_and_named(self):
        candidates = ev.hits_to_candidates([
            _hit("a", 0.9, audience="all", source="ok.md"),
            _hit("b", 0.8, audience="manager", source="leak.md"),
        ])
        violation, sources = ev.audience_violation(candidates, "employee")
        self.assertTrue(violation)
        self.assertEqual(sources, ["leak.md"])


class MeanTests(unittest.TestCase):
    def test_empty_list_is_none_not_an_exception_or_zero(self):
        self.assertIsNone(ev.mean([]))

    def test_averages_normally(self):
        self.assertEqual(ev.mean([1.0, 2.0, 3.0]), 2.0)


class ScoreAnswerTests(unittest.TestCase):
    @patch("eval.refused")
    @patch("eval.faithfulness")
    def test_refusal_question_only_calls_refused(self, fake_faithfulness, fake_refused):
        fake_refused.return_value = True
        result = ev.score_answer(_q(expect_refusal=True), ["not found"], "I don't have that.")
        self.assertEqual(result, {"refusal_ok": True})
        fake_faithfulness.assert_not_called()

    @patch("eval.completeness")
    @patch("eval.context_relevance")
    @patch("eval.faithfulness")
    def test_normal_question_calls_all_three_judges(self, fake_f, fake_r, fake_c):
        fake_f.return_value = (0.9, "faithful reason")
        fake_r.return_value = (0.8, "relevance reason")
        fake_c.return_value = (0.7, "completeness reason")
        result = ev.score_answer(_q(), ["ctx"], "the answer")
        self.assertEqual(result["faithfulness"], 0.9)
        self.assertEqual(result["context_relevance"], 0.8)
        self.assertEqual(result["completeness"], 0.7)
        self.assertEqual(result["faithfulness_reason"], "faithful reason")
        self.assertNotIn("refusal_ok", result)


class LoadQuestionsTests(unittest.TestCase):
    def test_reads_jsonl_lines_into_dicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval_questions.jsonl"
            path.write_text(
                json.dumps(_q(id="A")) + "\n" + json.dumps(_q(id="B")) + "\n\n",
                encoding="utf-8",
            )
            with patch.object(ev, "QUESTIONS_FILE", path):
                questions = ev.load_questions()
        self.assertEqual([q["id"] for q in questions], ["A", "B"])

    def test_default_path_is_the_project_level_data_file(self):
        self.assertEqual(ev.QUESTIONS_FILE, Path(ev.__file__).resolve().parent / "data" / "eval_questions.jsonl")


# ---------------------------------------------------------------------------
# evaluate_question() — call-sharing rules, retrieval strategy, structure.
# ---------------------------------------------------------------------------

BASELINE_HITS = [_hit(f"base-{i}", 1.0 - i * 0.1) for i in range(4)]
FILTER_HITS = [_hit(f"filt-{i}", 1.0 - i * 0.1) for i in range(4)]
RERANK_ONLY_POOL = [_hit(f"ro-{i}", 1.0 - i * 0.05) for i in range(10)]
FR_POOL = [_hit(f"fr-{i}", 1.0 - i * 0.05) for i in range(10)]
RO_SCORES = [0.1, 0.9, 0.3, 0.8, 0.2, 0.95, 0.05, 0.15, 0.25, 0.35]
FR_SCORES = [0.95, 0.85, 0.75, 0.65, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0]  # 4 clear 0.6


class EvaluateQuestionCallSharingTests(unittest.TestCase):
    def setUp(self):
        self.q = _q()

    def _run(self, planned_subjects=("pay_and_benefits",)):
        planned_subjects = list(planned_subjects)
        with patch("eval.plan_subjects", return_value=planned_subjects) as spy_plan, \
             patch("eval.knn_search") as spy_knn, \
             patch("eval.rerank_all") as spy_rerank, \
             patch("eval.answer", return_value="the answer"), \
             patch("eval.faithfulness", return_value=(0.8, "ok")), \
             patch("eval.context_relevance", return_value=(0.7, "ok")), \
             patch("eval.completeness", return_value=(0.9, "ok")), \
             patch("eval.refused", return_value=False):

            def knn_side_effect(client, query, audience, subjects=None, top_k=4, updated_after=None):
                if top_k == ev.BASELINE_TOP_K and subjects is None:
                    return BASELINE_HITS
                if top_k == ev.BASELINE_TOP_K:
                    return FILTER_HITS
                if top_k == ev.CANDIDATE_POOL_SIZE and subjects is None:
                    return RERANK_ONLY_POOL
                return FR_POOL

            def rerank_side_effect(query, candidates):
                scores = RO_SCORES if candidates[0]["text"].startswith("ro-") else FR_SCORES
                return sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)

            spy_knn.side_effect = knn_side_effect
            spy_rerank.side_effect = rerank_side_effect
            result = ev.evaluate_question(CLIENT, self.q)
            return result, spy_plan, spy_knn, spy_rerank

    def test_planner_called_exactly_once(self):
        _, spy_plan, _, _ = self._run()
        spy_plan.assert_called_once_with(self.q["question"])

    def test_planner_result_reused_by_every_subject_filter_config(self):
        planned = ["pay_and_benefits", "time_off_and_leave"]
        result, _, _, _ = self._run(planned_subjects=planned)
        self.assertEqual(result["configs"]["filter-only"]["retrieval"]["subjects_applied"], planned)
        self.assertEqual(result["configs"]["filter + rerank static"]["retrieval"]["subjects_applied"], planned)
        self.assertEqual(result["configs"]["filter + rerank dynamic"]["retrieval"]["subjects_applied"], planned)

    def test_baseline_and_rerank_only_do_not_apply_the_plan(self):
        result, _, _, _ = self._run()
        self.assertIsNone(result["configs"]["baseline"]["retrieval"]["subjects_applied"])
        self.assertIsNone(result["configs"]["rerank-only"]["retrieval"]["subjects_applied"])

    def test_baseline_uses_top_k_4(self):
        _, _, spy_knn, _ = self._run()
        calls = spy_knn.call_args_list
        top_ks = [c.kwargs.get("top_k", c.args[4] if len(c.args) > 4 else None) for c in calls]
        self.assertIn(ev.BASELINE_TOP_K, top_ks)

    def test_rerank_configs_use_candidate_pool_10(self):
        _, _, spy_knn, _ = self._run()
        top_ks = [c.kwargs.get("top_k") for c in spy_knn.call_args_list]
        self.assertEqual(top_ks.count(ev.CANDIDATE_POOL_SIZE), 2)  # rerank-only pool + filter+rerank pool

    def test_reranker_called_exactly_twice_total(self):
        # once for rerank-only's own pool, once (shared) for the filter+rerank pool.
        _, _, _, spy_rerank = self._run()
        self.assertEqual(spy_rerank.call_count, 2)

    def test_baseline_and_filter_only_never_call_reranker(self):
        # If rerank_all were (incorrectly) called for these, call_count would exceed 2.
        _, _, _, spy_rerank = self._run()
        self.assertEqual(spy_rerank.call_count, 2)

    def test_rerank_only_uses_no_subject_filter(self):
        _, _, spy_knn, _ = self._run()
        pool_call = next(c for c in spy_knn.call_args_list if c.kwargs.get("top_k") == ev.CANDIDATE_POOL_SIZE
                          and c.kwargs.get("subjects") is None)
        self.assertIsNone(pool_call.kwargs["subjects"])

    def test_static_selection_keeps_exactly_3(self):
        result, _, _, _ = self._run()
        self.assertEqual(result["configs"]["filter + rerank static"]["n_chunks"], 3)
        self.assertEqual(result["configs"]["rerank-only"]["n_chunks"], 3)

    def test_dynamic_selection_keeps_all_scores_at_or_above_0_6(self):
        result, _, _, _ = self._run()
        # FR_SCORES has exactly 4 values >= 0.6.
        self.assertEqual(result["configs"]["filter + rerank dynamic"]["n_chunks"], 4)

    def test_dynamic_returns_not_found_when_pool_has_no_qualifying_score(self):
        with patch("eval.plan_subjects", return_value=["pay_and_benefits"]), \
             patch("eval.knn_search") as spy_knn, \
             patch("eval.rerank_all") as spy_rerank, \
             patch("eval.answer", return_value="not found in context"), \
             patch("eval.faithfulness", return_value=(0.1, "ok")), \
             patch("eval.context_relevance", return_value=(0.1, "ok")), \
             patch("eval.completeness", return_value=(0.0, "ok")), \
             patch("eval.refused", return_value=False):
            spy_knn.side_effect = lambda client, query, audience, subjects=None, top_k=4, updated_after=None: (
                BASELINE_HITS if top_k == ev.BASELINE_TOP_K and subjects is None else
                FILTER_HITS if top_k == ev.BASELINE_TOP_K else
                RERANK_ONLY_POOL if subjects is None else FR_POOL
            )
            low_scores = [0.1] * 10
            spy_rerank.side_effect = lambda query, candidates: sorted(
                zip(candidates, RO_SCORES if candidates[0]["text"].startswith("ro-") else low_scores),
                key=lambda p: p[1], reverse=True,
            )
            result = ev.evaluate_question(CLIENT, self.q)
        self.assertEqual(result["configs"]["filter + rerank dynamic"]["contexts"], ["not found"])
        self.assertEqual(result["configs"]["filter + rerank dynamic"]["n_chunks"], 1)

    def test_answer_receives_contexts_in_relevance_order(self):
        result, _, _, _ = self._run()
        static_ctx = result["configs"]["filter + rerank static"]["contexts"]
        # FR_SCORES best-first: index 0 (0.95), 1 (0.85), 2 (0.75) -> "fr-0", "fr-1", "fr-2".
        self.assertEqual(static_ctx, ["fr-0", "fr-1", "fr-2"])

    def test_refusal_question_records_refusal_ok_and_skips_content_judges(self):
        refusal_q = _q(expect_refusal=True, question="what was the AWS bill?")
        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", return_value=BASELINE_HITS), \
             patch("eval.rerank_all") as spy_rerank, \
             patch("eval.answer", return_value="I don't have that information."), \
             patch("eval.faithfulness") as spy_faith, \
             patch("eval.context_relevance"), patch("eval.completeness"), \
             patch("eval.refused", return_value=True):
            spy_rerank.side_effect = lambda query, candidates: [(c, 0.5) for c in candidates]
            result = ev.evaluate_question(CLIENT, refusal_q)
        for name in ev.CONFIG_NAMES:
            self.assertEqual(result["configs"][name]["metrics"], {"refusal_ok": True})
        spy_faith.assert_not_called()

    def test_security_violation_is_recorded_and_not_silently_fixed(self):
        leaking_hits = [_hit("ok", 0.9, audience="all", source="ok.md"),
                        _hit("leak", 0.8, audience="manager", source="leak.md")]
        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", return_value=leaking_hits), \
             patch("eval.rerank_all", return_value=[]), \
             patch("eval.answer", return_value="the answer"), \
             patch("eval.faithfulness", return_value=(0.5, "ok")), \
             patch("eval.context_relevance", return_value=(0.5, "ok")), \
             patch("eval.completeness", return_value=(0.5, "ok")), \
             patch("eval.refused", return_value=False):
            result = ev.evaluate_question(CLIENT, _q(audience="employee"))
        baseline = result["configs"]["baseline"]["retrieval"]
        self.assertTrue(baseline["security_violation"])
        self.assertIn("leak.md", baseline["security_violating_sources"])
        # eval must not remove the leaked chunk from the context -- it exposes, never fixes.
        self.assertIn("leak", result["configs"]["baseline"]["contexts"])


# ---------------------------------------------------------------------------
# evaluate() / report() — full structure, aggregation, presentation.
# ---------------------------------------------------------------------------

class EvaluateAndReportTests(unittest.TestCase):
    def _evaluate_two_questions(self):
        normal_q = _q(id="NORMAL", expect_refusal=False)
        refusal_q = _q(id="REFUSAL", expect_refusal=True, question="what was the AWS bill?")

        def fake_knn(client, query, audience, subjects=None, top_k=4, updated_after=None):
            if top_k == ev.BASELINE_TOP_K:
                return BASELINE_HITS if subjects is None else FILTER_HITS
            return RERANK_ONLY_POOL if subjects is None else FR_POOL

        def fake_rerank(query, candidates):
            scores = RO_SCORES if candidates[0]["text"].startswith("ro-") else FR_SCORES
            return sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)

        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", side_effect=fake_knn), \
             patch("eval.rerank_all", side_effect=fake_rerank), \
             patch("eval.answer", side_effect=lambda q, c: "I don't have that." if "AWS" in q else "the answer"), \
             patch("eval.faithfulness", return_value=(0.8, "ok")), \
             patch("eval.context_relevance", return_value=(0.7, "ok")), \
             patch("eval.completeness", return_value=(0.9, "ok")), \
             patch("eval.refused", side_effect=lambda a: "don't have" in a.lower()):
            return ev.evaluate(CLIENT, [normal_q, refusal_q])

    def test_evaluate_returns_structured_data_not_only_printed_output(self):
        results = self._evaluate_two_questions()
        self.assertIn("metadata", results)
        self.assertIn("questions", results)
        self.assertIn("summary", results)
        self.assertEqual(set(results["questions"]), {"NORMAL", "REFUSAL"})
        self.assertEqual(results["metadata"]["question_count"], 2)
        self.assertEqual(results["metadata"]["candidate_pool_size"], ev.CANDIDATE_POOL_SIZE)

    def test_summary_averages_only_the_normal_question_for_content_judges(self):
        results = self._evaluate_two_questions()
        summary = results["summary"]["baseline"]
        self.assertEqual(summary["faithfulness_avg"], 0.8)  # only NORMAL contributes
        self.assertEqual(summary["refusal_ok_avg"], 1.0)    # only REFUSAL contributes, and it passed

    def test_report_runs_against_the_structured_result_without_crashing(self):
        results = self._evaluate_two_questions()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            ev.report(results)
        output = buf.getvalue()
        for name in ev.CONFIG_NAMES:
            self.assertIn(name, output)

    def test_report_does_not_mutate_or_require_reevaluation(self):
        results = self._evaluate_two_questions()
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            ev.report(results)
        # Still fully usable afterward -- report() is read-only presentation.
        self.assertEqual(results["metadata"]["question_count"], 2)


if __name__ == "__main__":
    unittest.main()
