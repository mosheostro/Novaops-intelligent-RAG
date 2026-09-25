"""Deterministic tests for eval.py and its domain model contract (models.py) —
no network, no AWS, no real credentials.

knn_search, rerank_all, plan_subjects, answer and the judges are all patched
where eval.py imported them (`eval.<name>`), so no test ever reaches Bedrock or
OpenSearch. A bare object() stands in for the OpenSearch client throughout,
since eval.py never calls anything on it directly — only knn_search (mocked)
receives it. `eval.rerank_all` is patched at the point eval.py's own
`rerank_candidates` adapter calls it — the mock therefore receives the small
single-field {"text": ...} dicts that adapter builds, exactly like the real
reranker.rerank_all would.
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
import models  # noqa: E402

CLIENT = object()  # eval.py must never call anything on this directly


def _hit(text, score, audience="all", subjects=None, source="doc.md",
         corpus="handbook", last_updated="2024-01-01"):
    return {"_score": score, "_source": {
        "text": text, "source": source, "corpus": corpus,
        "audience": audience, "subjects": subjects or [], "last_updated": last_updated,
    }}


def _q(id="Q1", question="how much severance do I get?", audience="employee",
       expect_refusal=False, key_facts=None, report=False):
    return {"id": id, "question": question, "audience": audience,
            "expect_refusal": expect_refusal, "key_facts": key_facts or ["fact one"],
            "report": report}


# ---------------------------------------------------------------------------
# Domain model contract (models.py) — no eval.py involved at all.
# ---------------------------------------------------------------------------

def _candidate(**overrides):
    fields = dict(
        text="chunk text", source="doc.md", corpus="handbook", audience="all",
        subjects=[], last_updated="2024-01-01", vector_score=0.9, vector_rank=0,
    )
    fields.update(overrides)
    return models.Candidate(**fields)


class ModelContractTests(unittest.TestCase):
    def test_candidate_is_immutable(self):
        c = _candidate()
        with self.assertRaises(Exception):
            c.rerank_score = 0.5  # frozen -- must raise, never silently succeed

    def test_selected_chunk_carries_final_rank_separately_from_candidate(self):
        c = _candidate()
        self.assertFalse(hasattr(c, "final_rank"))  # Candidate never has one
        sc = models.SelectedChunk(candidate=c, final_rank=3)
        self.assertEqual(sc.final_rank, 3)
        self.assertIs(sc.candidate, c)  # same object, not a copy

    def test_selected_chunk_is_also_immutable(self):
        sc = models.SelectedChunk(candidate=_candidate(), final_rank=0)
        with self.assertRaises(Exception):
            sc.final_rank = 1

    def test_security_audit_has_no_score_field_and_is_not_an_evaluation_type(self):
        audit = models.SecurityAudit(violation=True, violating_sources=["leak.md"])
        self.assertFalse(hasattr(audit, "faithfulness"))
        self.assertFalse(hasattr(audit, "refusal_ok"))
        self.assertNotIsInstance(audit, (models.ContentEvaluation, models.RefusalEvaluation))

    def test_content_and_refusal_evaluation_discriminate_by_kind(self):
        content = models.ContentEvaluation(
            faithfulness=0.8, faithfulness_reason="ok", context_relevance=0.7,
            context_relevance_reason="ok", completeness=0.9, completeness_reason="ok",
        )
        refusal = models.RefusalEvaluation(refusal_ok=True)
        self.assertEqual(content.kind, "content")
        self.assertEqual(refusal.kind, "refusal")
        self.assertIsInstance(content, models.ContentEvaluation)
        self.assertNotIsInstance(content, models.RefusalEvaluation)

    def test_configuration_result_evaluation_union_rejects_unknown_kind(self):
        retrieval = models.RetrievalResult(
            audience="employee", subjects_applied=None, top_k_requested=4,
            candidates=[_candidate()], security=models.SecurityAudit(violation=False, violating_sources=[]),
        )
        selection = models.SelectionResult(status="not_found", chunks=[], context_texts=["not found"])
        with self.assertRaises(Exception):
            models.ConfigurationResult(
                name="baseline", retrieval=retrieval, selection=selection, answer="x",
                evaluation={"kind": "bogus"},
            )

    def test_invalid_config_name_is_rejected(self):
        retrieval = models.RetrievalResult(
            audience="employee", subjects_applied=None, top_k_requested=4,
            candidates=[], security=models.SecurityAudit(violation=False, violating_sources=[]),
        )
        selection = models.SelectionResult(status="not_found", chunks=[], context_texts=["not found"])
        with self.assertRaises(Exception):
            models.ConfigurationResult(
                name="not-a-real-config", retrieval=retrieval, selection=selection, answer="x",
                evaluation=models.RefusalEvaluation(refusal_ok=True),
            )

    def test_selection_status_rejects_values_outside_the_literal(self):
        with self.assertRaises(Exception):
            models.SelectionResult(status="maybe", chunks=[], context_texts=["not found"])

    def test_not_found_selection_has_zero_chunks_but_context_texts_present(self):
        sel = models.SelectionResult(status="not_found", chunks=[], context_texts=["not found"])
        self.assertEqual(sel.chunks, [])
        self.assertEqual(sel.context_texts, ["not found"])

    def test_configuration_result_n_chunks_is_computed_not_stored(self):
        retrieval = models.RetrievalResult(
            audience="manager", subjects_applied=None, top_k_requested=10,
            candidates=[_candidate()], security=models.SecurityAudit(violation=False, violating_sources=[]),
        )
        empty_selection = models.SelectionResult(status="not_found", chunks=[], context_texts=["not found"])
        cfg = models.ConfigurationResult(
            name="rerank-only", retrieval=retrieval, selection=empty_selection, answer="x",
            evaluation=models.RefusalEvaluation(refusal_ok=False),
        )
        self.assertEqual(cfg.n_chunks, 0)
        self.assertNotIn("n_chunks", models.ConfigurationResult.model_fields)  # not a stored field

        chunk = models.SelectedChunk(candidate=_candidate(), final_rank=0)
        cfg2 = cfg.model_copy(update={"selection": models.SelectionResult(
            status="selected", chunks=[chunk], context_texts=["chunk text"],
        )})
        self.assertEqual(cfg2.n_chunks, 1)


# ---------------------------------------------------------------------------
# Pure helpers in eval.py — no mocking needed at all.
# ---------------------------------------------------------------------------

class HitsToCandidatesTests(unittest.TestCase):
    def test_preserves_all_metadata_and_zero_based_vector_rank(self):
        hits = [_hit("a", 0.9), _hit("b", 0.8, audience="manager", subjects=["x"])]
        candidates = ev.hits_to_candidates(hits)
        self.assertIsInstance(candidates[0], models.Candidate)
        self.assertEqual(candidates[0].vector_rank, 0)
        self.assertEqual(candidates[1].vector_rank, 1)
        self.assertEqual(candidates[0].vector_score, 0.9)
        self.assertEqual(candidates[1].audience, "manager")
        self.assertEqual(candidates[1].subjects, ["x"])
        self.assertIsNone(candidates[0].rerank_score)


class RerankCandidatesAndAttachScoresTests(unittest.TestCase):
    @patch("eval.rerank_all")
    def test_rerank_candidates_projects_only_text_to_the_untouched_reranker(self, fake_rerank_all):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8)])
        fake_rerank_all.side_effect = lambda query, cands: list(zip(cands, [0.3, 0.7]))
        ev.rerank_candidates("q", candidates)
        (_, passed_dicts), _ = fake_rerank_all.call_args
        self.assertEqual(passed_dicts, [{"text": "a"}, {"text": "b"}])

    @patch("eval.rerank_all")
    def test_rerank_candidates_maps_scores_back_to_original_candidates(self, fake_rerank_all):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8)])
        fake_rerank_all.side_effect = lambda query, cands: [(cands[1], 0.7), (cands[0], 0.3)]
        ranked = ev.rerank_candidates("q", candidates)
        self.assertEqual([(c.text, s) for c, s in ranked], [("b", 0.7), ("a", 0.3)])
        self.assertIs(ranked[0][0], candidates[1])
        self.assertIs(ranked[1][0], candidates[0])

    def test_attach_rerank_scores_is_pure_candidate_stays_untouched(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8)])
        original = candidates[0]
        ranked = [(candidates[1], 0.7), (candidates[0], 0.3)]
        updated_pool, updated_ranked = ev.attach_rerank_scores(candidates, ranked)
        self.assertIsNone(original.rerank_score)  # the ORIGINAL Candidate is untouched (frozen)
        self.assertEqual(updated_pool[0].rerank_score, 0.3)
        self.assertEqual(updated_pool[1].rerank_score, 0.7)

    def test_attach_rerank_scores_preserves_vector_order_in_pool(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8), _hit("c", 0.7)])
        ranked = [(candidates[2], 0.9), (candidates[0], 0.5), (candidates[1], 0.1)]  # rerank order != vector order
        updated_pool, _ = ev.attach_rerank_scores(candidates, ranked)
        self.assertEqual([c.text for c in updated_pool], ["a", "b", "c"])  # still vector order

    def test_attach_rerank_scores_ranked_output_preserves_best_first_order(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8), _hit("c", 0.7)])
        ranked = [(candidates[2], 0.9), (candidates[0], 0.5), (candidates[1], 0.1)]
        _, updated_ranked = ev.attach_rerank_scores(candidates, ranked)
        self.assertEqual([c.text for c, _ in updated_ranked], ["c", "a", "b"])

    def test_attach_rerank_scores_pool_and_ranked_share_identical_updated_instances(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8)])
        ranked = [(candidates[0], 0.3), (candidates[1], 0.7)]
        updated_pool, updated_ranked = ev.attach_rerank_scores(candidates, ranked)
        # The pool's "a" candidate IS the same object as the ranked list's "a" entry.
        pool_a = next(c for c in updated_pool if c.text == "a")
        ranked_a = next(c for c, _ in updated_ranked if c.text == "a")
        self.assertIs(pool_a, ranked_a)


class SelectContextTests(unittest.TestCase):
    def _ranked(self, scores):
        candidates = ev.hits_to_candidates([_hit(f"c{i}", 1.0 - i * 0.01) for i in range(len(scores))])
        return list(zip(candidates, scores))

    def test_static_keeps_exactly_top_k_best_first(self):
        ranked = self._ranked([0.95, 0.85, 0.75, 0.65, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0])
        selected = ev.select_context(ranked, "static", static_k=ev.RERANK_STATIC_TOP_K)
        self.assertEqual([c.text for c, _ in selected], ["c0", "c1", "c2"])

    def test_dynamic_keeps_every_score_at_or_above_threshold(self):
        # 4 of 10 candidates clear 0.6 -- dynamic must keep all 4, not static's 3.
        ranked = self._ranked([0.95, 0.85, 0.75, 0.65, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0])
        selected = ev.select_context(ranked, "dynamic", min_score=ev.MIN_RERANK_SCORE)
        self.assertEqual([c.text for c, _ in selected], ["c0", "c1", "c2", "c3"])

    def test_dynamic_returns_empty_when_nothing_clears_the_bar(self):
        ranked = self._ranked([0.3, 0.2, 0.1])
        selected = ev.select_context(ranked, "dynamic", min_score=ev.MIN_RERANK_SCORE)
        self.assertEqual(selected, [])  # NOT a top-1 fallback; select_context itself has no sentinel

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            ev.select_context(self._ranked([0.5]), "bogus")


class BuildSelectionResultTests(unittest.TestCase):
    def test_nonempty_selection_has_status_selected(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8)])
        result = ev.build_selection_result([(candidates[0], 0.9), (candidates[1], 0.7)])
        self.assertEqual(result.status, "selected")
        self.assertEqual([sc.final_rank for sc in result.chunks], [0, 1])
        self.assertEqual(result.context_texts, ["a", "b"])

    def test_empty_selection_is_not_found_with_the_literal_sentinel_text(self):
        result = ev.build_selection_result([])
        self.assertEqual(result.status, "not_found")
        self.assertEqual(result.chunks, [])
        self.assertEqual(result.context_texts, ["not found"])  # NOT derived from an empty chunk list


class SelectAllTests(unittest.TestCase):
    def test_keeps_every_candidate_final_rank_equals_vector_rank(self):
        pool = ev.hits_to_candidates([_hit("a", 0.9), _hit("b", 0.8), _hit("c", 0.7)])
        result = ev._select_all(pool)
        self.assertEqual(result.status, "selected")
        self.assertEqual([sc.final_rank for sc in result.chunks], [0, 1, 2])
        self.assertEqual([sc.candidate.vector_rank for sc in result.chunks], [0, 1, 2])
        self.assertEqual(result.context_texts, ["a", "b", "c"])

    def test_empty_pool_is_not_found(self):
        result = ev._select_all([])
        self.assertEqual(result.status, "not_found")
        self.assertEqual(result.context_texts, ["not found"])


class AuditSecurityTests(unittest.TestCase):
    def test_manager_role_is_never_flagged(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9, audience="manager")])
        audit = ev.audit_security(candidates, "manager")
        self.assertIsInstance(audit, models.SecurityAudit)
        self.assertFalse(audit.violation)
        self.assertEqual(audit.violating_sources, [])

    def test_employee_with_only_all_audience_is_clean(self):
        candidates = ev.hits_to_candidates([_hit("a", 0.9, audience="all")])
        audit = ev.audit_security(candidates, "employee")
        self.assertFalse(audit.violation)

    def test_employee_with_a_manager_chunk_is_flagged_and_named(self):
        candidates = ev.hits_to_candidates([
            _hit("a", 0.9, audience="all", source="ok.md"),
            _hit("b", 0.8, audience="manager", source="leak.md"),
        ])
        audit = ev.audit_security(candidates, "employee")
        self.assertTrue(audit.violation)
        self.assertEqual(audit.violating_sources, ["leak.md"])


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
        self.assertIsInstance(result, models.RefusalEvaluation)
        self.assertTrue(result.refusal_ok)
        fake_faithfulness.assert_not_called()

    @patch("eval.completeness")
    @patch("eval.context_relevance")
    @patch("eval.faithfulness")
    def test_normal_question_calls_all_three_judges(self, fake_f, fake_r, fake_c):
        fake_f.return_value = (0.9, "faithful reason")
        fake_r.return_value = (0.8, "relevance reason")
        fake_c.return_value = (0.7, "completeness reason")
        result = ev.score_answer(_q(), ["ctx"], "the answer")
        self.assertIsInstance(result, models.ContentEvaluation)
        self.assertEqual(result.faithfulness, 0.9)
        self.assertEqual(result.context_relevance, 0.8)
        self.assertEqual(result.completeness, 0.7)
        self.assertEqual(result.faithfulness_reason, "faithful reason")


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

    def test_report_flag_is_preserved_through_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval_questions.jsonl"
            path.write_text(
                json.dumps(_q(id="A", report=True)) + "\n" + json.dumps(_q(id="B", report=False)) + "\n",
                encoding="utf-8",
            )
            with patch.object(ev, "QUESTIONS_FILE", path):
                questions = ev.load_questions()
        by_id = {q["id"]: q for q in questions}
        self.assertIs(by_id["A"]["report"], True)
        self.assertIs(by_id["B"]["report"], False)


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
                # `candidates` here are the adapter's {"text": ...} dicts.
                scores = RO_SCORES if candidates[0]["text"].startswith("ro-") else FR_SCORES
                return sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)

            spy_knn.side_effect = knn_side_effect
            spy_rerank.side_effect = rerank_side_effect
            result = ev.evaluate_question(CLIENT, self.q)
            return result, spy_plan, spy_knn, spy_rerank

    def test_returns_a_question_result(self):
        result, _, _, _ = self._run()
        self.assertIsInstance(result, models.QuestionResult)
        self.assertEqual(set(result.configurations), set(models.CONFIG_NAMES))

    def test_planner_called_exactly_once(self):
        _, spy_plan, _, _ = self._run()
        spy_plan.assert_called_once_with(self.q["question"])

    def test_planner_result_reused_by_every_subject_filter_config(self):
        planned = ["pay_and_benefits", "time_off_and_leave"]
        result, _, _, _ = self._run(planned_subjects=planned)
        self.assertEqual(result.configurations["filter-only"].retrieval.subjects_applied, planned)
        self.assertEqual(result.configurations["filter + rerank static"].retrieval.subjects_applied, planned)
        self.assertEqual(result.configurations["filter + rerank dynamic"].retrieval.subjects_applied, planned)

    def test_baseline_and_rerank_only_do_not_apply_the_plan(self):
        result, _, _, _ = self._run()
        self.assertIsNone(result.configurations["baseline"].retrieval.subjects_applied)
        self.assertIsNone(result.configurations["rerank-only"].retrieval.subjects_applied)

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
        self.assertEqual(result.configurations["filter + rerank static"].n_chunks, 3)
        self.assertEqual(result.configurations["rerank-only"].n_chunks, 3)

    def test_dynamic_selection_keeps_all_scores_at_or_above_0_6(self):
        result, _, _, _ = self._run()
        # FR_SCORES has exactly 4 values >= 0.6.
        self.assertEqual(result.configurations["filter + rerank dynamic"].n_chunks, 4)

    def test_static_and_dynamic_share_the_same_retrieval_result(self):
        # The semantic contract: ONE retrieval, two selection cuts. Verified as
        # literal object identity -- the design's resolved sharing decision.
        result, _, _, _ = self._run()
        static_cfg = result.configurations["filter + rerank static"]
        dynamic_cfg = result.configurations["filter + rerank dynamic"]
        self.assertIs(static_cfg.retrieval, dynamic_cfg.retrieval)
        self.assertIsNot(static_cfg.selection, dynamic_cfg.selection)  # different cuts

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
        dynamic = result.configurations["filter + rerank dynamic"]
        self.assertEqual(dynamic.selection.status, "not_found")
        self.assertEqual(dynamic.selection.chunks, [])
        self.assertEqual(dynamic.selection.context_texts, ["not found"])
        self.assertEqual(dynamic.n_chunks, 0)  # NOT len(["not found"]) == 1

    def test_answer_receives_contexts_in_relevance_order(self):
        result, _, _, _ = self._run()
        static_ctx = result.configurations["filter + rerank static"].selection.context_texts
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
        for name in models.CONFIG_NAMES:
            evaluation = result.configurations[name].evaluation
            self.assertIsInstance(evaluation, models.RefusalEvaluation)
            self.assertTrue(evaluation.refusal_ok)
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
        baseline = result.configurations["baseline"]
        self.assertTrue(baseline.retrieval.security.violation)
        self.assertIn("leak.md", baseline.retrieval.security.violating_sources)
        # Security is a separate concept from the quality metrics -- never folded in.
        self.assertFalse(hasattr(baseline.evaluation, "security_violation"))
        # eval must not remove the leaked chunk from the context -- it exposes, never fixes.
        self.assertIn("leak", baseline.selection.context_texts)


# ---------------------------------------------------------------------------
# evaluate() / report() — full structure, aggregation, presentation.
# ---------------------------------------------------------------------------

class EvaluateAndReportTests(unittest.TestCase):
    def _evaluate_two_questions(self, questions=None):
        questions = questions or [
            _q(id="NORMAL", expect_refusal=False),
            _q(id="REFUSAL", expect_refusal=True, question="what was the AWS bill?"),
        ]

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
            return ev.evaluate(CLIENT, questions), questions

    def test_evaluate_returns_an_evaluation_result_not_a_dict(self):
        results, _questions = self._evaluate_two_questions()
        self.assertIsInstance(results, models.EvaluationResult)
        self.assertEqual(set(results.questions), {"NORMAL", "REFUSAL"})
        self.assertEqual(results.metadata.question_count, 2)
        self.assertEqual(results.metadata.candidate_pool_size, ev.CANDIDATE_POOL_SIZE)

    def test_summary_averages_only_the_normal_question_for_content_judges(self):
        results, _questions = self._evaluate_two_questions()
        summary = results.summary["baseline"]
        self.assertEqual(summary.faithfulness_avg, 0.8)  # only NORMAL contributes
        self.assertEqual(summary.refusal_ok_avg, 1.0)    # only REFUSAL contributes, and it passed

    def test_summary_n_chunks_avg_uses_the_corrected_not_found_semantics(self):
        results, _questions = self._evaluate_two_questions()
        # FR_SCORES has exactly 4 values >= 0.6 for both questions -> dynamic n_chunks == 4 each.
        self.assertEqual(results.summary["filter + rerank dynamic"].n_chunks_avg, 4.0)

    def test_report_runs_against_the_structured_result_without_crashing(self):
        results, _questions = self._evaluate_two_questions()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            ev.report(results)
        output = buf.getvalue()
        for name in models.CONFIG_NAMES:
            self.assertIn(name, output)

    def test_report_with_no_questions_arg_prints_no_detailed_section(self):
        results, _questions = self._evaluate_two_questions()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            ev.report(results)  # backward-compatible call, unchanged behavior
        self.assertNotIn("SELECTED EVALUATION REPORT", buf.getvalue())

    def test_report_does_not_mutate_or_require_reevaluation(self):
        results, _questions = self._evaluate_two_questions()
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            ev.report(results)
        # Still fully usable afterward -- report() is read-only presentation.
        self.assertEqual(results.metadata.question_count, 2)

    def test_result_serializes_at_the_boundary_via_pydantic(self):
        # JSON only appears at an external boundary, produced directly from the
        # domain object -- never a hand-built dict staged in between.
        results, _questions = self._evaluate_two_questions()
        payload = results.model_dump_json()
        self.assertIsInstance(payload, str)
        restored = models.EvaluationResult.model_validate_json(payload)
        self.assertEqual(restored.metadata.question_count, results.metadata.question_count)


# ---------------------------------------------------------------------------
# The "report" flag and the detailed per-question report section.
#
# The flag lives ONLY on the raw input question dicts (from
# data/eval_questions.jsonl) -- it is never added to QuestionResult or any
# other domain model. report() takes the original `questions` list as an
# optional second argument purely to know which already-computed
# QuestionResults to print in detail; evaluation itself is entirely
# unaffected (evaluate() is called identically either way).
# ---------------------------------------------------------------------------

class TruncateAnswerTests(unittest.TestCase):
    def test_short_answer_is_unchanged(self):
        short = "a short answer"
        self.assertEqual(ev.truncate_answer(short, max_chars=ev.MAX_REPORT_ANSWER_CHARS), short)

    def test_answer_exactly_at_the_limit_is_unchanged(self):
        exact = "x" * ev.MAX_REPORT_ANSWER_CHARS
        self.assertEqual(ev.truncate_answer(exact, max_chars=ev.MAX_REPORT_ANSWER_CHARS), exact)

    def test_long_answer_is_truncated_predictably(self):
        long_answer = "y" * (ev.MAX_REPORT_ANSWER_CHARS + 50)
        result = ev.truncate_answer(long_answer, max_chars=ev.MAX_REPORT_ANSWER_CHARS)
        self.assertTrue(result.startswith("y" * ev.MAX_REPORT_ANSWER_CHARS))
        self.assertIn("[truncated]", result)
        self.assertLess(len(result), len(long_answer) + 30)

    def test_uses_the_module_default_when_max_chars_omitted(self):
        long_answer = "z" * (ev.MAX_REPORT_ANSWER_CHARS + 10)
        self.assertIn("[truncated]", ev.truncate_answer(long_answer))


class SelectedQuestionIdsTests(unittest.TestCase):
    def test_only_report_true_questions_are_selected(self):
        questions = [_q(id="A", report=True), _q(id="B", report=False), _q(id="C", report=True)]
        self.assertEqual(ev._selected_question_ids(questions), ["A", "C"])

    def test_missing_report_key_defaults_to_not_selected(self):
        questions = [{"id": "NO_FLAG", "question": "q", "audience": "employee",
                      "expect_refusal": False, "key_facts": []}]
        self.assertEqual(ev._selected_question_ids(questions), [])

    def test_no_selected_questions_is_an_empty_list_not_an_error(self):
        questions = [_q(id="A", report=False)]
        self.assertEqual(ev._selected_question_ids(questions), [])


class SelectedReportSectionTests(unittest.TestCase):
    """report(results, questions) — the human-readable detailed section."""

    def _run(self, questions):
        import io
        from contextlib import redirect_stdout

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
            results = ev.evaluate(CLIENT, questions)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ev.report(results, questions)
        return results, buf.getvalue()

    def test_report_false_questions_do_not_appear_in_detailed_section(self):
        questions = [_q(id="SHOWN", report=True), _q(id="HIDDEN", report=False, question="other question")]
        _results, output = self._run(questions)
        section = output.split("SELECTED EVALUATION REPORT", 1)[1]
        self.assertIn("SHOWN", section)
        self.assertNotIn("HIDDEN", section)

    def test_report_true_questions_appear(self):
        questions = [_q(id="SHOWN", report=True)]
        _results, output = self._run(questions)
        self.assertIn("SELECTED EVALUATION REPORT", output)
        self.assertIn("SHOWN", output)

    def test_selected_question_appears_exactly_once_under_all_five_configs(self):
        questions = [_q(id="SHOWN", report=True)]
        _results, output = self._run(questions)
        section = output.split("SELECTED EVALUATION REPORT", 1)[1]
        self.assertEqual(section.count("QUESTION: SHOWN"), 1)  # not once per config
        for name in models.CONFIG_NAMES:
            self.assertIn(name, section)

    def test_no_selected_questions_omits_the_section_entirely(self):
        questions = [_q(id="A", report=False), _q(id="B", report=False)]
        _results, output = self._run(questions)
        self.assertNotIn("SELECTED EVALUATION REPORT", output)

    def test_not_found_selection_is_displayed_correctly(self):
        # All FR_SCORES below 0.6 -> the dynamic config for this question is not_found.
        low_fr_scores = [0.1] * 10
        questions = [_q(id="SHOWN", report=True)]

        def fake_knn(client, query, audience, subjects=None, top_k=4, updated_after=None):
            if top_k == ev.BASELINE_TOP_K:
                return BASELINE_HITS if subjects is None else FILTER_HITS
            return RERANK_ONLY_POOL if subjects is None else FR_POOL

        def fake_rerank(query, candidates):
            scores = RO_SCORES if candidates[0]["text"].startswith("ro-") else low_fr_scores
            return sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)

        import io
        from contextlib import redirect_stdout
        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", side_effect=fake_knn), \
             patch("eval.rerank_all", side_effect=fake_rerank), \
             patch("eval.answer", return_value="not found in context"), \
             patch("eval.faithfulness", return_value=(0.1, "ok")), \
             patch("eval.context_relevance", return_value=(0.1, "ok")), \
             patch("eval.completeness", return_value=(0.0, "ok")), \
             patch("eval.refused", return_value=False):
            results = ev.evaluate(CLIENT, questions)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ev.report(results, questions)
        output = buf.getvalue()
        self.assertIn("not_found", output)
        self.assertIn("Selected chunks: 0", output)

    def test_refusal_question_displays_expected_refusal_information(self):
        questions = [_q(id="REFUSAL_Q", report=True, expect_refusal=True, question="what was the AWS bill?")]
        _results, output = self._run(questions)
        section = output.split("SELECTED EVALUATION REPORT", 1)[1]
        self.assertIn("REFUSAL_Q", section)
        self.assertIn("EXPECTED REFUSAL: True", section)

    def test_expect_refusal_true_but_chunks_selected_is_exposed_not_hidden(self):
        # baseline/filter-only always select something (no cut) -- for a
        # refusal question that means "expect_refusal=true" alongside
        # "Selected chunks: 4" for those two configs. The report must show
        # this plainly, not suppress or hide it.
        questions = [_q(id="REFUSAL_Q", report=True, expect_refusal=True, question="what was the AWS bill?")]
        _results, output = self._run(questions)
        section = output.split("SELECTED EVALUATION REPORT", 1)[1]
        baseline_block = section[section.index("\nbaseline\n"):section.index("\nfilter-only\n")]
        self.assertIn("Selected chunks: 4", baseline_block)

    def test_answer_truncation_in_report_does_not_modify_the_domain_answer(self):
        long_answer = "a" * (ev.MAX_REPORT_ANSWER_CHARS + 100)
        questions = [_q(id="SHOWN", report=True)]

        def fake_knn(client, query, audience, subjects=None, top_k=4, updated_after=None):
            if top_k == ev.BASELINE_TOP_K:
                return BASELINE_HITS if subjects is None else FILTER_HITS
            return RERANK_ONLY_POOL if subjects is None else FR_POOL

        def fake_rerank(query, candidates):
            scores = RO_SCORES if candidates[0]["text"].startswith("ro-") else FR_SCORES
            return sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)

        import io
        from contextlib import redirect_stdout
        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", side_effect=fake_knn), \
             patch("eval.rerank_all", side_effect=fake_rerank), \
             patch("eval.answer", return_value=long_answer), \
             patch("eval.faithfulness", return_value=(0.8, "ok")), \
             patch("eval.context_relevance", return_value=(0.7, "ok")), \
             patch("eval.completeness", return_value=(0.9, "ok")), \
             patch("eval.refused", return_value=False):
            results = ev.evaluate(CLIENT, questions)
        # The domain object holds the COMPLETE, untruncated answer.
        self.assertEqual(results.questions["SHOWN"].configurations["baseline"].answer, long_answer)
        buf = io.StringIO()
        with redirect_stdout(buf):
            ev.report(results, questions)
        # The printed report is bounded.
        self.assertNotIn(long_answer, buf.getvalue())
        self.assertIn("[truncated]", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
