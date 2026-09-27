"""An evaluation case whose role is not a supported audience is a deliberate
access-boundary test, not a crash: the RAG core still fails closed
(retrieval.access_filter raises), eval.py records the case per configuration
as an "access_violation" outcome with a deterministic refusal, spends no
model/OpenSearch call on it, and keeps evaluating every other question.

"access_violation" (request rejected — the boundary held) is kept apart from
SecurityAudit.violation / security_violations (a LEAK — the boundary failed),
from "not_found" (authorized, nothing relevant) and from real failures.
All model/network calls are patched on `eval.<name>`."""
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import eval as ev  # noqa: E402
import models  # noqa: E402

CLIENT = object()
ALL = list(models.CONFIG_NAMES)
UNSUPPORTED = ("HR", "", "Spiderman")


def _hit(i):
    return {"_score": 1.0 - i * 0.05, "_source": {
        "text": f"chunk {i}", "source": f"d{i}.md", "corpus": "handbook",
        "audience": "all", "subjects": [], "last_updated": "2024-01-01",
    }}


def _q(id="Q1", audience="employee", expect_refusal=False):
    return {"id": id, "question": f"question {id}?", "audience": audience,
            "expect_refusal": expect_refusal, "key_facts": [] if expect_refusal else ["fact"]}


class _Patched(unittest.TestCase):
    rerank_score = 0.9

    def setUp(self):
        self.plan = patch("eval.plan_subjects", return_value=["benefits"]).start()
        self.knn = patch("eval.knn_search",
                         side_effect=lambda c, q, role, subjects=None, top_k=4, updated_after=None:
                         [_hit(i) for i in range(top_k)]).start()
        self.rerank = patch("eval.rerank_all",
                            side_effect=lambda q, cands: [(c, self.rerank_score) for c in cands]).start()
        self.answer = patch("eval.answer", return_value="the answer").start()
        self.judges = [patch(f"eval.{name}", return_value=(1.0, name)).start()
                       for name in ("faithfulness", "context_relevance", "completeness")]
        self.judges.append(patch("eval.refusal", return_value=True).start())
        self.addCleanup(patch.stopall)

    def assert_no_calls(self):
        for mock in (self.plan, self.knn, self.rerank, self.answer, *self.judges):
            mock.assert_not_called()


class UnsupportedRoleTests(_Patched):
    def test_every_config_records_an_access_violation_with_the_deterministic_refusal(self):
        for role in UNSUPPORTED:
            for expect_refusal in (False, True):
                with self.subTest(role=role, expect_refusal=expect_refusal):
                    r = ev.evaluate_question(CLIENT, _q(audience=role, expect_refusal=expect_refusal))
                    self.assertEqual(list(r.configurations), ALL)
                    self.assertIsNone(r.planned_subjects)
                    for cfg in r.configurations.values():
                        self.assertEqual(cfg.selection.status, "access_violation")
                        self.assertEqual(cfg.selection.chunks, [])
                        self.assertEqual(cfg.n_chunks, 0)
                        self.assertEqual(cfg.answer, ev.ACCESS_DENIED_ANSWER)
                        self.assertIsInstance(cfg.evaluation, models.AccessViolationEvaluation)
                        self.assertEqual(cfg.retrieval.audience, role)
                        self.assertEqual(cfg.retrieval.candidates, [])
                        self.assertFalse(cfg.retrieval.security.violation)  # rejected, not leaked

    def test_zero_model_opensearch_or_judge_calls(self):
        for role in UNSUPPORTED:
            with self.subTest(role=role):
                ev.evaluate_question(CLIENT, _q(audience=role))
                self.assert_no_calls()

    def test_the_deterministic_answer_is_the_documented_refusal(self):
        self.assertEqual(ev.ACCESS_DENIED_ANSWER,
                         "Your current role is not supported by this system, so we cannot provide an answer.")

    def test_estimate_counts_no_calls_for_an_unsupported_role(self):
        self.assertEqual(ev.estimate_calls([_q(audience="HR")], ALL), 0)
        self.assertEqual(ev.estimate_calls([_q(audience="HR"), _q("Q2")], ALL), ev.estimate_calls([_q("Q2")], ALL))


class MixedRunTests(_Patched):
    def _run(self):
        questions = [_q("Q1"), _q("Q2", "manager"), _q("Q3", "HR"), _q("Q4")]
        return ev.evaluate(CLIENT, questions)

    def test_questions_after_the_violation_still_run(self):
        result = self._run()
        self.assertEqual(list(result.questions), ["Q1", "Q2", "Q3", "Q4"])
        for qid in ("Q1", "Q2", "Q4"):
            for cfg in result.questions[qid].configurations.values():
                self.assertIsInstance(cfg.evaluation, models.ContentEvaluation)
                self.assertEqual(cfg.answer, "the answer")
        self.assertEqual(self.plan.call_count, 3)  # once per VALID question only
        roles = {call.args[2] for call in self.knn.call_args_list}
        self.assertEqual(roles, {"employee", "manager"})  # never queried as "HR"

    def test_summary_counts_access_violations_apart_from_leaks_and_quality(self):
        for name, s in self._run().summary.items():
            with self.subTest(config=name):
                self.assertEqual(s.access_violations, 1)
                self.assertEqual(s.security_violations, 0)
                self.assertEqual(s.faithfulness_avg, 1.0)       # from the three answered questions only
                self.assertIsNotNone(s.n_chunks_avg)
                self.assertGreater(s.n_chunks_avg, 0)           # the rejected case adds no 0-chunk row
                self.assertIsNone(s.refusal_ok_avg)             # not scored as a refusal either

    def test_saved_run_round_trips_and_old_runs_still_load(self):
        result = self._run()
        again = models.EvaluationResult.model_validate_json(result.model_dump_json())
        self.assertEqual(again, result)
        old = result.model_dump(mode="json")
        for s in old["summary"].values():
            del s["access_violations"]                          # a run saved before the field existed
        self.assertEqual(models.EvaluationResult.model_validate(old).summary["baseline"].access_violations, 0)

    def test_cli_report_shows_the_outcome_without_judge_scores(self):
        result = self._run()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ev.report(result, [dict(_q("Q3", "HR"), report=True)])
        out = buf.getvalue()
        self.assertIn("access_viol", out)
        self.assertIn("Selection status: access_violation", out)
        self.assertIn("access violation — unsupported role 'HR'", out)


class NotFoundIsDistinctTests(_Patched):
    rerank_score = 0.1  # below MIN_RERANK_SCORE: authorized, but nothing relevant enough

    def test_authorized_not_found_is_not_an_access_violation(self):
        r = ev.evaluate_question(CLIENT, _q(), configs=["filter + rerank dynamic"])
        cfg = r.configurations["filter + rerank dynamic"]
        self.assertEqual(cfg.selection.status, "not_found")
        self.assertIsInstance(cfg.evaluation, models.ContentEvaluation)  # judged as usual
        self.assertNotEqual(cfg.answer, ev.ACCESS_DENIED_ANSWER)
        summary = ev.summarize({"Q1": r}, ["filter + rerank dynamic"])["filter + rerank dynamic"]
        self.assertEqual(summary.access_violations, 0)


class FailuresStillPropagateTests(_Patched):
    def test_an_infrastructure_failure_for_a_valid_role_is_not_swallowed(self):
        self.knn.side_effect = ConnectionError("opensearch down")
        with self.assertRaises(ConnectionError):
            ev.evaluate(CLIENT, [_q("Q1"), _q("Q2")])


if __name__ == "__main__":
    unittest.main()
