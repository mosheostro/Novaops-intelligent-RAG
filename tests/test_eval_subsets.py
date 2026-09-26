"""An experiment = selected questions × selected configurations × optional cutoff.

Covers the evaluation-layer contract the Dashboard launches through eval.py:
select_questions (subset of the canonical dataset), evaluate/evaluate_question
with a configuration subset (planner/rerank work still shared where it was
shared), the recency cutoff, estimate_calls, and the `scenario` field being
display-only. All model/network calls are patched on `eval.<name>`.
"""
import json
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import eval as ev  # noqa: E402
import models  # noqa: E402

CLIENT = object()
ALL = list(models.CONFIG_NAMES)


def _hit(i):
    return {"_score": 1.0 - i * 0.05, "_source": {
        "text": f"chunk {i}", "source": f"d{i}.md", "corpus": "handbook",
        "audience": "all", "subjects": [], "last_updated": "2024-01-01",
    }}


def _q(id="Q1", audience="employee", expect_refusal=False, **extra):
    return {"id": id, "question": f"question {id}?", "audience": audience,
            "expect_refusal": expect_refusal, "key_facts": [] if expect_refusal else ["fact"], **extra}


class _Patched(unittest.TestCase):
    def setUp(self):
        self.plan = patch("eval.plan_subjects", return_value=["benefits"]).start()
        self.knn = patch("eval.knn_search",
                         side_effect=lambda c, q, role, subjects=None, top_k=4, updated_after=None:
                         [_hit(i) for i in range(top_k)]).start()
        self.rerank = patch("eval.rerank_all",
                            side_effect=lambda q, cands: [(c, 0.9 - i * 0.1) for i, c in enumerate(cands)]).start()
        self.answer = patch("eval.answer", return_value="the answer").start()
        patch("eval.faithfulness", return_value=(1.0, "f")).start()
        patch("eval.context_relevance", return_value=(1.0, "r")).start()
        patch("eval.completeness", return_value=(1.0, "c")).start()
        patch("eval.refusal", return_value=True).start()
        self.addCleanup(patch.stopall)


class ConfigSubsetTests(_Patched):
    def test_baseline_only_runs_no_planner_and_no_rerank(self):
        r = ev.evaluate_question(CLIENT, _q(), configs=["baseline"])
        self.plan.assert_not_called()
        self.rerank.assert_not_called()
        self.assertEqual(self.knn.call_count, 1)
        self.assertEqual(list(r.configurations), ["baseline"])
        self.assertIsNone(r.planned_subjects)  # None = planner not run (distinct from [] = ran, found none)

    def test_dynamic_only_plans_once_and_reranks_once(self):
        r = ev.evaluate_question(CLIENT, _q(), configs=["filter + rerank dynamic"])
        self.assertEqual(self.plan.call_count, 1)
        self.assertEqual(self.rerank.call_count, 1)
        self.assertEqual(self.knn.call_count, 1)
        self.assertEqual(r.planned_subjects, ["benefits"])
        self.assertEqual(list(r.configurations), ["filter + rerank dynamic"])

    def test_static_and_dynamic_still_share_one_pool_and_one_rerank(self):
        r = ev.evaluate_question(CLIENT, _q(), configs=["filter + rerank dynamic", "filter + rerank static"])
        self.assertEqual(self.rerank.call_count, 1)
        self.assertEqual(self.knn.call_count, 1)
        self.assertIs(r.configurations["filter + rerank static"].retrieval,
                      r.configurations["filter + rerank dynamic"].retrieval)
        # canonical order, regardless of the order requested
        self.assertEqual(list(r.configurations), ["filter + rerank static", "filter + rerank dynamic"])

    def test_filter_only_and_dynamic_share_the_one_planner_call(self):
        ev.evaluate_question(CLIENT, _q(), configs=["filter-only", "filter + rerank dynamic"])
        self.assertEqual(self.plan.call_count, 1)

    def test_rerank_only_and_filter_rerank_are_two_pools_two_reranks(self):
        ev.evaluate_question(CLIENT, _q(), configs=["rerank-only", "filter + rerank static"])
        self.assertEqual(self.rerank.call_count, 2)

    def test_default_is_all_five_configs(self):
        r = ev.evaluate_question(CLIENT, _q())
        self.assertEqual(list(r.configurations), ALL)
        self.assertEqual(self.plan.call_count, 1)
        self.assertEqual(self.rerank.call_count, 2)

    def test_answers_and_judges_run_only_for_selected_configs(self):
        ev.evaluate_question(CLIENT, _q(), configs=["baseline", "rerank-only"])
        self.assertEqual(self.answer.call_count, 2)

    def test_unknown_or_empty_config_selection_is_rejected(self):
        with self.assertRaises(ValueError):
            ev.evaluate_question(CLIENT, _q(), configs=["best"])
        with self.assertRaises(ValueError):
            ev.evaluate_question(CLIENT, _q(), configs=[])
        self.knn.assert_not_called()


class CutoffTests(_Patched):
    def test_no_cutoff_passes_none(self):
        r = ev.evaluate_question(CLIENT, _q())
        self.assertTrue(all(c.kwargs.get("updated_after") is None for c in self.knn.call_args_list))
        self.assertIsNone(r.configurations["baseline"].retrieval.cutoff)

    def test_cutoff_reaches_every_retrieval_and_is_recorded(self):
        r = ev.evaluate_question(CLIENT, _q(), cutoff=date(2025, 4, 28))
        self.assertEqual(self.knn.call_count, 4)
        self.assertTrue(all(c.kwargs["updated_after"] == "2025-04-28" for c in self.knn.call_args_list))
        self.assertTrue(all(c.args[2] == "employee" for c in self.knn.call_args_list))  # access still applied
        for cfg in r.configurations.values():
            self.assertEqual(cfg.retrieval.cutoff, date(2025, 4, 28))


class EvaluateSubsetTests(_Patched):
    def test_metadata_records_configs_in_canonical_order_and_cutoff(self):
        result = ev.evaluate(CLIENT, [_q("A"), _q("B", expect_refusal=True)],
                             configs=["filter + rerank dynamic", "baseline"], cutoff=date(2025, 1, 1))
        self.assertEqual(result.metadata.configs, ["baseline", "filter + rerank dynamic"])
        self.assertEqual(result.metadata.cutoff, date(2025, 1, 1))
        self.assertEqual(result.metadata.question_count, 2)
        self.assertEqual(list(result.summary), ["baseline", "filter + rerank dynamic"])
        self.assertEqual(list(result.questions), ["A", "B"])

    def test_default_evaluate_is_unchanged_all_configs_no_cutoff(self):
        result = ev.evaluate(CLIENT, [_q("A")])
        self.assertEqual(result.metadata.configs, ALL)
        self.assertIsNone(result.metadata.cutoff)
        self.assertEqual(list(result.summary), ALL)

    def test_saved_runs_without_cutoff_still_load(self):
        result = ev.evaluate(CLIENT, [_q("A")])
        data = json.loads(result.model_dump_json())
        del data["metadata"]["cutoff"]
        self.assertIsNone(models.EvaluationResult.model_validate(data).metadata.cutoff)

    def test_report_prints_only_the_selected_configs(self):
        result = ev.evaluate(CLIENT, [_q("A", report=True)], configs=["baseline"])
        with patch("builtins.print") as p:
            ev.report(result, [_q("A", report=True)])
        printed = "\n".join(str(c.args[0]) if c.args else "" for c in p.call_args_list)
        self.assertIn("baseline", printed)
        self.assertNotIn("filter + rerank dynamic", printed)


class SelectQuestionsTests(unittest.TestCase):
    QS = [_q("A"), _q("B"), _q("C")]

    def test_none_selects_everything(self):
        self.assertEqual(ev.select_questions(self.QS, None), self.QS)

    def test_subset_keeps_dataset_order_not_request_order(self):
        self.assertEqual([q["id"] for q in ev.select_questions(self.QS, ["C", "A"])], ["A", "C"])

    def test_unknown_id_is_an_error_naming_it(self):
        with self.assertRaisesRegex(ValueError, "NOPE"):
            ev.select_questions(self.QS, ["A", "NOPE"])

    def test_empty_selection_is_an_error(self):
        with self.assertRaises(ValueError):
            ev.select_questions(self.QS, [])


class EstimateCallsTests(unittest.TestCase):
    """planner + one embedding per distinct pool + one rerank per reranked pool
    + one answer per config + judges (3 per config, or 1 for refusal cases)."""

    def test_all_configs_answerable_question(self):
        self.assertEqual(ev.estimate_calls([_q()], ALL), 1 + 4 + 2 + 5 + 15)

    def test_all_configs_refusal_question(self):
        self.assertEqual(ev.estimate_calls([_q(expect_refusal=True)], ALL), 1 + 4 + 2 + 5 + 5)

    def test_baseline_only(self):
        self.assertEqual(ev.estimate_calls([_q()], ["baseline"]), 0 + 1 + 0 + 1 + 3)

    def test_static_and_dynamic_share_pool_and_rerank(self):
        self.assertEqual(ev.estimate_calls([_q()], ["filter + rerank static", "filter + rerank dynamic"]),
                         1 + 1 + 1 + 2 + 6)

    def test_sums_over_questions(self):
        self.assertEqual(ev.estimate_calls([_q("A"), _q("B", expect_refusal=True)], ["baseline"]), 5 + 3)


class ScenarioIsDisplayOnlyTests(_Patched):
    def test_evaluator_output_and_calls_do_not_depend_on_scenario(self):
        plain = ev.evaluate_question(CLIENT, _q())
        calls_plain = [c.kwargs for c in self.knn.call_args_list]
        self.knn.reset_mock()
        tagged = ev.evaluate_question(CLIENT, _q(scenario="access_boundary"))
        self.assertEqual([c.kwargs for c in self.knn.call_args_list], calls_plain)
        self.assertEqual(tagged, plain)


class CanonicalDatasetTests(unittest.TestCase):
    PATH = Path(ev.__file__).resolve().parent / "data" / "eval_questions.jsonl"
    SCENARIOS = {"standard", "cross_source", "access_boundary", "out_of_corpus"}

    def test_every_record_has_a_known_scenario_and_unique_id(self):
        records = ev.load_questions(self.PATH)
        self.assertTrue(records)
        self.assertEqual(len({r["id"] for r in records}), len(records))
        for r in records:
            with self.subTest(id=r["id"]):
                self.assertIn(r.get("scenario"), self.SCENARIOS)

    def test_short_debug_set_is_gone(self):
        self.assertFalse((self.PATH.parent / "eval_questions_short.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
