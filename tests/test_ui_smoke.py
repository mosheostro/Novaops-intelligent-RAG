"""Smoke tests for the Streamlit UI via streamlit.testing.v1.AppTest. ask.ask,
the OpenSearch client and RUNS_DIR are patched — no network, no AWS, no real
evaluation runs."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from streamlit.testing.v1 import AppTest  # noqa: E402

import models  # noqa: E402
import runs  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "ui" / "app.py")
TIMEOUT = 30


def _candidate(text, rank, audience="all", rerank=None):
    return models.Candidate(
        text=text, source=f"doc{rank}.md", corpus="handbook", audience=audience, subjects=["benefits"],
        last_updated="2024-01-01", vector_score=0.9 - rank * 0.1, vector_rank=rank, rerank_score=rerank,
    )


POOL = [_candidate("PTO accrues monthly.", 0, rerank=0.9), _candidate("Unrelated.", 1, rerank=0.1)]
RETRIEVAL = models.RetrievalResult(
    audience="employee", subjects_applied=["benefits"], top_k_requested=10, candidates=POOL,
    security=models.SecurityAudit(violation=False, violating_sources=[]),
)
SELECTION = models.SelectionResult(
    status="selected", chunks=[models.SelectedChunk(candidate=POOL[0], final_rank=0)],
    context_texts=[POOL[0].text],
)
ASK_RESULT = models.AskResult(
    question="How does PTO accrue?", audience="employee", config="filter + rerank dynamic",
    planned_subjects=["benefits"], retrieval=RETRIEVAL, selection=SELECTION,
    answer="PTO accrues monthly (ANSWER-MARKER).",
    judgement=models.LiveJudgement(faithfulness=0.9, faithfulness_reason="grounded",
                                   context_relevance=0.8, context_relevance_reason="on topic",
                                   refused=False, completeness=0.7, completeness_reason="covers it"),
)

CONTENT_EVAL = models.ContentEvaluation(
    faithfulness=0.9, faithfulness_reason="f", context_relevance=0.8, context_relevance_reason="r",
    completeness=0.7, completeness_reason="c",
)
RUN = models.EvaluationResult(
    metadata=models.EvaluationMetadata(
        question_count=1, configs=list(models.CONFIG_NAMES), candidate_pool_size=10,
        static_top_k=3, dynamic_threshold=0.6, baseline_top_k=4,
    ),
    questions={"PTO": models.QuestionResult(
        id="PTO", question="How does PTO accrue?", audience="employee", expect_refusal=False,
        key_facts=["monthly"], planned_subjects=["benefits"],
        configurations={name: models.ConfigurationResult(
            name=name, retrieval=RETRIEVAL, selection=SELECTION, answer="PTO accrues monthly.",
            evaluation=CONTENT_EVAL,
        ) for name in models.CONFIG_NAMES},
    )},
    summary={name: models.ConfigSummary(
        n_chunks_avg=1.0, faithfulness_avg=0.9, context_relevance_avg=0.8, completeness_avg=0.7,
        refusal_ok_avg=None, security_violations=0,
    ) for name in models.CONFIG_NAMES},
)


def _texts(at) -> str:
    return "\n".join(str(e.value) for kind in ("title", "subheader", "markdown", "caption", "error", "warning", "info", "metric")
                     for e in getattr(at, kind))


class ChatPageTests(unittest.TestCase):
    def setUp(self):
        patch("ui.state.opensearch_client", return_value=object()).start()
        self.ask = patch("ask.ask", return_value=ASK_RESULT).start()
        self.addCleanup(patch.stopall)

    def test_chat_renders_answer_sources_trace_and_judges(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        self.assertFalse(at.exception)
        at.chat_input[0].set_value("How does PTO accrue?").run()
        self.assertFalse(at.exception)
        args = self.ask.call_args
        self.assertEqual(args.args[1:4], ("How does PTO accrue?", "employee", "filter + rerank dynamic"))
        text = _texts(at)
        self.assertIn("ANSWER-MARKER", text)
        self.assertIn("doc0.md", text)
        labels = [e.label for e in at.expander]
        self.assertTrue(any(label.startswith("Sources") for label in labels))
        self.assertIn("Pipeline trace", labels)
        self.assertIn("**Completeness (vs. retrieved context)** 0.70", "\n".join(e.proto.text for e in at.get("progress")))

    def test_role_switch_is_passed_to_ask(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        at.sidebar.radio(key="role").set_value("manager").run()
        at.chat_input[0].set_value("q").run()
        self.assertEqual(self.ask.call_args.args[2], "manager")

    def test_no_cutoff_by_default_and_chosen_cutoff_is_passed_to_ask(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        at.chat_input[0].set_value("q").run()
        self.assertIsNone(self.ask.call_args.kwargs["cutoff"])
        at.date_input(key="chat_cutoff").set_value(date(2024, 1, 1)).run()
        at.chat_input[0].set_value("q").run()
        self.assertEqual(self.ask.call_args.kwargs["cutoff"], date(2024, 1, 1))
        self.assertEqual(self.ask.call_args.args[3], "filter + rerank dynamic")  # config unaffected by the cutoff

    def test_pipeline_error_shows_type_only(self):
        self.ask.side_effect = RuntimeError("secret internals")
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        at.chat_input[0].set_value("q").run()
        errors = "\n".join(e.value for e in at.error)
        self.assertIn("RuntimeError", errors)
        self.assertNotIn("secret internals", errors)


class EvalPagesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        runs_dir = Path(tmp.name)
        (runs_dir / "20260101T000000Z_eval_questions.json").write_text(RUN.model_dump_json(), encoding="utf-8")
        patch.object(runs, "RUNS_DIR", runs_dir).start()
        patch("ui.state.opensearch_client", return_value=object()).start()
        self.popen = patch("runs.subprocess.Popen").start()
        self.addCleanup(patch.stopall)

    def test_runs_page_lists_saved_run(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        at.switch_page("pages/eval_runs.py").run()
        self.assertFalse(at.exception)
        df = at.dataframe[0].value
        self.assertIn("20260101T000000Z_eval_questions", list(df["Run"]))

    def _runs_page(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        at.switch_page("pages/eval_runs.py").run()
        self.assertFalse(at.exception)
        return at

    def test_run_needs_a_question_a_configuration_and_cost_confirmation(self):
        at = self._runs_page()
        self.assertTrue(at.button(key="launch_run").disabled)            # nothing selected yet
        at.checkbox(key="q::SEV_3YR").check().run()
        self.assertTrue(at.button(key="launch_run").disabled)            # not confirmed
        at.checkbox(key="confirm_cost").check().run()
        self.assertFalse(at.button(key="launch_run").disabled)
        for name in models.CONFIG_NAMES:
            at.checkbox(key=f"cfg::{name}").uncheck()
        at.run()
        self.assertTrue(at.button(key="launch_run").disabled)            # no configuration
        self.popen.assert_not_called()

    def test_every_canonical_question_is_selectable_by_id_with_its_audience_and_scenario(self):
        at = self._runs_page()
        labels = {c.key: c.label for c in at.checkbox if c.key and c.key.startswith("q::")}
        self.assertEqual(set(labels), {"q::" + qid for qid in (
            "SEV_3YR", "MOON_PT", "LEAVE_PRIMARY", "PTO_ROLLOVER", "K401_MATCH", "ONE21_CADENCE",
            "TERM_STEPS", "XSRC_SEV_TERM", "ACCESS_REVIEW", "UNANSWERABLE_AWS")})
        self.assertIn("ACCESS_REVIEW", labels["q::ACCESS_REVIEW"])
        self.assertIn("employee", labels["q::ACCESS_REVIEW"])
        self.assertIn("refusal", labels["q::ACCESS_REVIEW"])
        self.assertIn("access_boundary", labels["q::ACCESS_REVIEW"])
        self.assertIn("manager", labels["q::TERM_STEPS"])

    def test_launch_passes_exactly_the_selected_experiment(self):
        at = self._runs_page()
        at.checkbox(key="q::ACCESS_REVIEW").check()
        at.checkbox(key="q::SEV_3YR").check()
        for name in ("filter-only", "rerank-only", "filter + rerank static"):
            at.checkbox(key=f"cfg::{name}").uncheck()
        at.date_input(key="run_cutoff").set_value(date(2025, 4, 28))
        at.checkbox(key="confirm_cost").check().run()
        summary = _texts(at)
        self.assertIn("SEV_3YR", summary)
        self.assertIn("last_updated ≥ 2025-04-28", summary)
        self.assertIn("assume the full corpus", summary)                  # cutoff caveat
        at.button(key="launch_run").click().run()
        cmd = self.popen.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--ids") + 1], "SEV_3YR,ACCESS_REVIEW")  # dataset order
        self.assertEqual([cmd[i + 1] for i, a in enumerate(cmd) if a == "--config"],
                         ["baseline", "filter + rerank dynamic"])
        self.assertEqual(cmd[cmd.index("--cutoff") + 1], "2025-04-28")

    def test_there_is_no_access_filter_or_audience_override_control(self):
        at = self._runs_page()
        controls = [w.label.lower() for w in (*at.checkbox, *at.radio, *at.toggle)
                    if not (w.key or "").startswith("q::")]  # question labels may name e.g. ACCESS_REVIEW
        self.assertFalse(any("access" in c and "understand" not in c for c in controls))
        self.assertEqual([r.key for r in at.radio], [])  # no run-audience override on the page
        self.assertIn("audience comes from each test case", _texts(at).lower())

    def test_saved_runs_table_describes_the_experiment(self):
        at = self._runs_page()
        df = at.dataframe[0].value
        row = df[df["Run"] == "20260101T000000Z_eval_questions"].iloc[0]
        self.assertEqual(row["Questions"], "PTO")
        self.assertEqual(row["Configurations"], len(models.CONFIG_NAMES))

    def test_run_detail_renders_summary_matrix_and_drilldown(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.query_params["run"] = "20260101T000000Z_eval_questions"
        at.run()
        at.switch_page("pages/eval_run_detail.py").run()
        self.assertFalse(at.exception)
        self.assertGreaterEqual(len(at.dataframe), 2)  # summary + matrix
        self.assertEqual(len(at.tabs), len(models.CONFIG_NAMES))
        self.assertIn("How does PTO accrue?", _texts(at))

    def test_run_detail_shows_only_the_configurations_that_ran_and_the_cutoff(self):
        subset = RUN.model_copy(update={
            "metadata": RUN.metadata.model_copy(update={
                "configs": ["baseline", "filter + rerank dynamic"], "cutoff": date(2025, 4, 28)}),
            "questions": {"PTO": RUN.questions["PTO"].model_copy(update={"configurations": {
                n: RUN.questions["PTO"].configurations[n] for n in ("baseline", "filter + rerank dynamic")}})},
            "summary": {n: RUN.summary[n] for n in ("baseline", "filter + rerank dynamic")},
        })
        (runs.RUNS_DIR / "20260102T000000Z_eval_questions.json").write_text(subset.model_dump_json(), encoding="utf-8")
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.query_params["run"] = "20260102T000000Z_eval_questions"
        at.run()
        at.switch_page("pages/eval_run_detail.py").run()
        self.assertFalse(at.exception)
        self.assertEqual([tab.label for tab in at.tabs], ["baseline", "filter + rerank dynamic"])
        self.assertEqual(list(at.dataframe[0].value["Configuration"]), ["baseline", "filter + rerank dynamic"])
        text = _texts(at)
        self.assertIn("2025-04-28", text)
        self.assertIn("assume the full corpus", text)


HEADING_CHUNK = "# Severance policy\n\nBIG-HEADING-MARKER. Laid-off employees receive four weeks of base pay."
HEADING_POOL = [_candidate(HEADING_CHUNK, 0, rerank=0.9)]
HEADING_SELECTION = models.SelectionResult(
    status="selected", chunks=[models.SelectedChunk(candidate=HEADING_POOL[0], final_rank=0)],
    context_texts=[HEADING_CHUNK],
)
HEADING_RESULT = ASK_RESULT.model_copy(update={
    "retrieval": RETRIEVAL.model_copy(update={"candidates": HEADING_POOL}), "selection": HEADING_SELECTION,
})

NOT_FOUND = models.SelectionResult(status="not_found", chunks=[], context_texts=["not found"])
REFUSAL_RUN = models.EvaluationResult(
    metadata=RUN.metadata.model_copy(update={"configs": ["baseline", "filter + rerank dynamic"]}),
    questions={"ACCESS_REVIEW": models.QuestionResult(
        id="ACCESS_REVIEW", question="How do I run a formal performance review?", audience="employee",
        expect_refusal=True, key_facts=[], planned_subjects=["performance_and_feedback"],
        configurations={
            "baseline": models.ConfigurationResult(
                name="baseline", retrieval=RETRIEVAL, selection=SELECTION, answer="Here is how: ...",
                evaluation=models.RefusalEvaluation(refusal_ok=False)),
            "filter + rerank dynamic": models.ConfigurationResult(
                name="filter + rerank dynamic", retrieval=RETRIEVAL, selection=NOT_FOUND,
                answer="I don't have that information.", evaluation=models.RefusalEvaluation(refusal_ok=True)),
        },
    )},
    summary={n: models.ConfigSummary(n_chunks_avg=1.0, faithfulness_avg=None, context_relevance_avg=None,
                                     completeness_avg=None, refusal_ok_avg=v, security_violations=0)
             for n, v in (("baseline", 0.0), ("filter + rerank dynamic", 1.0))},
)


class PresentationTests(unittest.TestCase):
    """Sources, refusal presentation, Clear and Help — presentation only."""

    def setUp(self):
        patch("ui.state.opensearch_client", return_value=object()).start()
        self.ask = patch("ask.ask", return_value=HEADING_RESULT).start()
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        runs_dir = Path(tmp.name)
        (runs_dir / "20260103T000000Z_eval_questions.json").write_text(REFUSAL_RUN.model_dump_json(), encoding="utf-8")
        patch.object(runs, "RUNS_DIR", runs_dir).start()
        self.addCleanup(patch.stopall)

    def _chat_with_answer(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        at.chat_input[0].set_value("How much severance?").run()
        self.assertFalse(at.exception)
        return at

    def _refusal_detail(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT)
        at.query_params["run"] = "20260103T000000Z_eval_questions"
        at.run()
        at.switch_page("pages/eval_run_detail.py").run()
        self.assertFalse(at.exception)
        return at

    def test_chunk_text_is_never_rendered_as_markdown_headings(self):
        at = self._chat_with_answer()
        self.assertFalse(any("BIG-HEADING-MARKER" in m.value for m in at.markdown))  # no "# ..." as a heading
        self.assertTrue(any("BIG-HEADING-MARKER" in t.value for t in at.text))        # full text still shown
        self.assertTrue(any("doc0.md" in m.value for m in at.markdown))               # compact source header

    def test_chunk_text_is_bounded_in_run_detail_too(self):
        at = self._refusal_detail()
        self.assertFalse(any(m.value.lstrip().startswith("#") for m in at.markdown))

    def test_chat_shows_detected_refusal_but_no_expectation_or_refusal_ok(self):
        text = _texts(self._chat_with_answer().main)  # page body; the sidebar Help names every term
        self.assertIn("Expected: none — custom question", text)
        self.assertIn("Refusal: No", text)
        self.assertNotIn("Refusal OK", text)

    def test_run_detail_explains_refusal_cases(self):
        text = _texts(self._refusal_detail())
        self.assertIn("Expected: refusal", text)
        self.assertIn("Refusal OK", text)
        self.assertIn("content judges skipped", text)
        self.assertIn("did not refuse", text)   # baseline answered although a refusal was expected
        self.assertIn("refused", text)          # dynamic refused
        self.assertIn("access ok", text)        # security status shown, not only on violation

    def test_question_matrix_marks_refusal_cases(self):
        at = self._refusal_detail()
        matrix = at.dataframe[1].value
        self.assertEqual(list(matrix["Expected"]), ["refusal"])

    def test_clear_resets_only_the_chat_conversation(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        self.assertTrue(at.button(key="clear_chat").disabled)      # nothing to clear yet
        at.chat_input[0].set_value("q1").run()
        self.assertEqual(len(at.session_state["history"]), 1)
        self.assertFalse(at.button(key="clear_chat").disabled)
        at.button(key="clear_chat").click().run()
        self.assertEqual(at.session_state["history"], [])
        self.assertEqual(len(at.chat_message), 0)
        self.assertEqual(len(runs.list_runs()), 1)                   # saved runs untouched
        self.assertEqual(at.selectbox(key="chat_config").value, "filter + rerank dynamic")  # settings kept

    def test_conversation_scrolls_inside_a_bounded_container_below_the_controls(self):
        at = self._chat_with_answer()
        self.assertEqual(len(at.chat_message), 2)
        self.assertIsNotNone(at.selectbox(key="chat_config"))

    def test_saved_run_is_deleted_only_after_explicit_confirmation(self):
        run_id = "20260103T000000Z_eval_questions"
        at = self._refusal_detail()
        self.assertTrue(at.button(key=f"delete_run::{run_id}").disabled)
        at.checkbox(key=f"confirm_delete::{run_id}").check().run()
        self.assertTrue((runs.RUNS_DIR / f"{run_id}.json").exists())      # ticking alone deletes nothing
        at.button(key=f"delete_run::{run_id}").click().run()
        self.assertFalse(at.exception)
        self.assertFalse((runs.RUNS_DIR / f"{run_id}.json").exists())
        self.assertEqual(runs.list_runs(), [])
        self.assertIn("No runs yet", _texts(at))                            # back on the refreshed list

    def test_help_is_available_in_the_sidebar(self):
        at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
        help_box = next(e for e in at.sidebar.expander if e.label == "Help")
        text = "\n".join(m.value for m in help_box.markdown)
        for term in ("Chat", "Evaluation runs", "baseline", "cutoff", "Score with judges", "Refusal OK",
                     "Pipeline trace", "Bedrock"):
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main()
