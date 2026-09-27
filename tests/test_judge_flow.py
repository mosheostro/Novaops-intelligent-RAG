"""Judge self-test: the complete flow question → expectation → judge execution
→ domain model → UI, for the three cases the system distinguishes.

Only the model/network edges are patched (knn_search, plan_subjects,
rerank_all, answer, and the four judges at the module that imported them).
Everything between them runs for real: eval.evaluate / ask.ask, the Pydantic
models, JSON persistence under RUNS_DIR, and the Streamlit pages via AppTest.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")
os.environ.setdefault("APP_PASSWORD", "test-password")  # the UI refuses to run without one

from streamlit.testing.v1 import AppTest  # noqa: E402

import eval as ev  # noqa: E402
import models  # noqa: E402
import runs  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "ui" / "app.py")


def _app():
    """An AppTest of the dashboard, already signed in — the password gate itself
    is tested in test_access.py."""
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["authenticated"] = True
    return at
CLIENT = object()
REFUSAL_TEXT = "I don't have that information in the provided context."


def _hits(c, q, role, subjects=None, top_k=4, updated_after=None):
    return [{"_score": 0.9 - i * 0.05, "_source": {
        "text": f"evidence {i}", "source": f"d{i}.md", "corpus": "handbook", "audience": "all",
        "subjects": [], "last_updated": "2024-01-01"}} for i in range(top_k)]


def _ui_text(at) -> str:
    """Rendered text of the page body only — the sidebar Help mentions every term."""
    main = at.main
    parts = [str(e.value) for kind in ("markdown", "caption", "warning", "error", "success")
             for e in getattr(main, kind)]
    parts += [e.proto.text for e in main.get("progress")]  # judge score bars carry "**Label** 0.00"
    return "\n".join(parts)


ANSWERABLE = {"id": "ANS", "question": "How much severance?", "audience": "employee", "expect_refusal": False,
              "key_facts": ["4 weeks base", "2 weeks per year"]}
EXPECTED_REFUSAL = {"id": "REF", "question": "What was the AWS bill?", "audience": "employee",
                    "expect_refusal": True, "key_facts": []}


class BatchJudgeFlowTests(unittest.TestCase):
    def setUp(self):
        patch("eval.knn_search", side_effect=_hits).start()
        patch("eval.plan_subjects", return_value=[]).start()
        patch("eval.rerank_all", side_effect=lambda q, cands: [(c, 0.9) for c in cands]).start()
        # the dynamic config "refuses", every other config answers
        self.answer = patch("eval.answer", side_effect=lambda q, ctx: "Four weeks plus two per year.").start()
        self.faith = patch("eval.faithfulness", return_value=(0.91, "faithful-reason")).start()
        self.rel = patch("eval.context_relevance", return_value=(0.82, "relevance-reason")).start()
        self.comp = patch("eval.completeness", return_value=(0.73, "completeness-reason")).start()
        self.refusal = patch("eval.refusal", side_effect=lambda q, a: a == REFUSAL_TEXT).start()
        self.ctx_comp = patch("judges.context_completeness").start()
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        patch.object(ev, "RUNS_DIR", Path(tmp.name)).start()
        patch.object(runs, "RUNS_DIR", Path(tmp.name)).start()
        patch("ui.state.opensearch_client", return_value=object()).start()
        self.addCleanup(patch.stopall)

    def _detail(self, result, run_id):
        # run ids are unique per test: the detail page caches loaded runs by id (runs are immutable)
        ev.save_result(result, run_id)                   # the same persistence path a real run uses
        at = _app()
        at.query_params["run"] = run_id
        at.run()
        at.switch_page("app_pages/eval_run_detail.py").run()
        self.assertFalse(at.exception)
        return at

    def test_answerable_case_runs_all_content_judges_and_completeness_reaches_the_ui(self):
        result = ev.evaluate(CLIENT, [ANSWERABLE], configs=["baseline"])
        self.comp.assert_called_once_with(ANSWERABLE["question"], ANSWERABLE["key_facts"],
                                          "Four weeks plus two per year.")
        self.refusal.assert_not_called()                 # batch semantics unchanged: no refusal judge here
        self.ctx_comp.assert_not_called()                # the Chat-only completeness mode never runs in batch
        evaluation = result.questions["ANS"].configurations["baseline"].evaluation
        self.assertEqual((evaluation.kind, evaluation.faithfulness, evaluation.context_relevance,
                          evaluation.completeness), ("content", 0.91, 0.82, 0.73))
        self.assertEqual(result.summary["baseline"].completeness_avg, 0.73)
        text = _ui_text(self._detail(result, "FLOW_ANSWERABLE"))
        for shown in ("**Faithfulness** 0.91", "**Context relevance** 0.82", "**Completeness** 0.73",
                      "completeness-reason", "Expected: answer", "Refusal: not judged"):
            self.assertIn(shown, text)
        self.assertNotIn("vs. retrieved context", text)  # the two completeness metrics are never mixed

    def test_expected_refusal_case_runs_only_the_refusal_judge_and_compares_expected_vs_actual(self):
        self.answer.side_effect = lambda q, ctx: REFUSAL_TEXT if ctx == ["not found"] else "Roughly $40k."
        self.rerank = patch("eval.rerank_all", side_effect=lambda q, cands: [(c, 0.1) for c in cands]).start()
        result = ev.evaluate(CLIENT, [EXPECTED_REFUSAL], configs=["baseline", "filter + rerank dynamic"])
        self.faith.assert_not_called()
        self.rel.assert_not_called()
        self.comp.assert_not_called()
        self.assertEqual(self.refusal.call_count, 2)
        cfgs = result.questions["REF"].configurations
        self.assertFalse(cfgs["baseline"].evaluation.refusal_ok)                # answered -> not OK
        self.assertTrue(cfgs["filter + rerank dynamic"].evaluation.refusal_ok)  # refused  -> OK
        self.assertEqual(result.summary["baseline"].refusal_ok_avg, 0.0)
        self.assertIsNone(result.summary["baseline"].completeness_avg)          # skipped, not zero
        text = _ui_text(self._detail(result, "FLOW_REFUSAL"))
        for shown in ("Expected: refusal", "did not refuse", "refused", "Refusal OK ✗", "Refusal OK ✓",
                      "content judges skipped"):
            self.assertIn(shown, text)
        self.assertNotIn("**Completeness**", text)


class ChatJudgeFlowTests(unittest.TestCase):
    def setUp(self):
        patch("ui.state.opensearch_client", return_value=object()).start()
        patch("ask.knn_search", side_effect=_hits).start()
        patch("ask.plan_subjects", return_value=[]).start()
        patch("eval.rerank_all", side_effect=lambda q, cands: [(c, 0.9) for c in cands]).start()
        self.answer = patch("ask.answer", return_value=REFUSAL_TEXT).start()
        self.faith = patch("ask.faithfulness", return_value=(0.64, "faith-reason")).start()
        self.rel = patch("ask.context_relevance", return_value=(0.55, "rel-reason")).start()
        self.refusal = patch("ask.refusal", side_effect=lambda q, a: a == REFUSAL_TEXT).start()
        self.comp = patch("judges.completeness").start()
        self.ctx_comp = patch("ask.context_completeness", return_value=(0.66, "ctx-completeness-reason")).start()
        self.addCleanup(patch.stopall)

    def _ask(self, question="What was the AWS bill?", judged=True):
        at = _app().run()
        if judged:
            at.toggle(key="chat_judge").set_value(True).run()
        at.chat_input[0].set_value(question).run()
        self.assertFalse(at.exception)
        return at

    def test_custom_question_with_judges_shows_detected_refusal_without_refusal_ok(self):
        at = self._ask()
        self.refusal.assert_called_once_with("What was the AWS bill?", REFUSAL_TEXT)  # same judge as batch
        self.comp.assert_not_called()
        self.ctx_comp.assert_not_called()                # refusal -> no usable context -> no extra call
        judgement = at.session_state["history"][0].judgement
        self.assertTrue(judgement.refused)
        self.assertIsNone(judgement.completeness)
        text = _ui_text(at)
        for shown in ("Refusal: Yes", "**Faithfulness** 0.64", "**Context relevance** 0.55",
                      "Expected: none — custom question", "Completeness (vs. retrieved context)",
                      "n/a — no usable context"):
            self.assertIn(shown, text)
        self.assertNotIn("Refusal OK", text)

    def test_custom_question_answered_normally_runs_all_four_judges_and_shows_them(self):
        self.answer.return_value = "PTO accrues monthly."
        at = self._ask("How does PTO accrue?")
        self.ctx_comp.assert_called_once()
        question, contexts, answer = self.ctx_comp.call_args.args
        self.assertEqual((question, answer), ("How does PTO accrue?", "PTO accrues monthly."))
        self.assertEqual(contexts, at.session_state["history"][0].selection.context_texts)
        self.assertEqual(at.session_state["history"][0].judgement.completeness, 0.66)
        text = _ui_text(at)
        for shown in ("Refusal: No", "**Faithfulness** 0.64", "**Context relevance** 0.55",
                      "**Completeness (vs. retrieved context)** 0.66", "ctx-completeness-reason"):
            self.assertIn(shown, text)
        self.assertNotIn("Refusal: Yes", text)
        self.assertNotIn("n/a", text)

    def test_without_judges_no_judge_runs_and_no_judge_result_is_shown(self):
        at = self._ask(judged=False)
        self.refusal.assert_not_called()
        self.faith.assert_not_called()
        self.ctx_comp.assert_not_called()
        self.assertIsNone(at.session_state["history"][0].judgement)
        self.assertNotIn("Refusal:", _ui_text(at))


if __name__ == "__main__":
    unittest.main()
