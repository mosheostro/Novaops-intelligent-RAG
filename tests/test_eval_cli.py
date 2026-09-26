"""eval.py command line: --questions picks the question set, --save persists the
EvaluationResult as JSON under RUNS_DIR (what the UI dashboard browses).
evaluate/report are patched — these tests cover only the CLI wiring."""
import json
import os
import re
import tempfile
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


def _rec(qid):
    return {"id": qid, "question": f"{qid}?", "audience": "employee", "expect_refusal": False, "key_facts": []}

RESULT = models.EvaluationResult(
    metadata=models.EvaluationMetadata(
        question_count=0, configs=list(models.CONFIG_NAMES), candidate_pool_size=10,
        static_top_k=3, dynamic_threshold=0.6, baseline_top_k=4,
    ),
    questions={},
    summary={},
)


class _CliTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.runs_dir = self.tmp / "runs"
        for p in (
            patch("eval.configure_logging"),
            patch("eval.opensearch_client", return_value=CLIENT),
            patch("eval.evaluate", return_value=RESULT),
            patch("eval.report"),
            patch.object(ev, "RUNS_DIR", self.runs_dir),
        ):
            p.start()
        self.addCleanup(patch.stopall)
        self.questions = self.tmp / "set.jsonl"
        self.questions.write_text(json.dumps(_rec("A")) + "\n", encoding="utf-8")


class EvalCliTests(_CliTestCase):
    def test_no_flags_saves_nothing(self):
        with patch("eval.load_questions", return_value=[]):
            ev.main([])
        self.assertFalse(self.runs_dir.exists())

    def test_questions_flag_loads_that_file(self):
        with patch("eval.evaluate", return_value=RESULT) as evaluate:
            ev.main(["--questions", str(self.questions)])
        self.assertEqual(evaluate.call_args.args[1], [_rec("A")])

    def test_save_with_run_id_writes_round_trippable_json(self):
        ev.main(["--questions", str(self.questions), "--save", "--run-id", "R1"])
        path = self.runs_dir / "R1.json"
        self.assertTrue(path.is_file())
        self.assertEqual(models.EvaluationResult.model_validate_json(path.read_text(encoding="utf-8")), RESULT)

    def test_save_without_run_id_names_file_by_utc_timestamp_and_question_set(self):
        ev.main(["--questions", str(self.questions), "--save"])
        [path] = self.runs_dir.glob("*.json")
        self.assertRegex(path.name, re.compile(r"^\d{8}T\d{6}Z_set\.json$"))


class ExperimentSelectionCliTests(_CliTestCase):
    """--ids / --config / --cutoff: the experiment the Dashboard launches."""

    def setUp(self):
        super().setUp()
        self.questions.write_text("\n".join(json.dumps(_rec(i)) for i in ("A", "B", "C")) + "\n",
                                  encoding="utf-8")
        self.evaluate = patch("eval.evaluate", return_value=RESULT).start()

    def test_ids_select_a_subset_of_the_dataset_in_file_order(self):
        ev.main(["--questions", str(self.questions), "--ids", "C,A"])
        self.assertEqual(self.evaluate.call_args.args[1], [_rec("A"), _rec("C")])

    def test_no_ids_no_config_no_cutoff_means_everything_as_before(self):
        ev.main(["--questions", str(self.questions)])
        self.assertEqual(len(self.evaluate.call_args.args[1]), 3)
        self.assertEqual(list(self.evaluate.call_args.kwargs["configs"]), list(models.CONFIG_NAMES))
        self.assertIsNone(self.evaluate.call_args.kwargs["cutoff"])

    def test_repeatable_config_and_cutoff_are_passed_through(self):
        ev.main(["--questions", str(self.questions), "--config", "baseline",
                 "--config", "filter + rerank dynamic", "--cutoff", "2025-04-28"])
        self.assertEqual(self.evaluate.call_args.kwargs["configs"], ["baseline", "filter + rerank dynamic"])
        self.assertEqual(self.evaluate.call_args.kwargs["cutoff"], date(2025, 4, 28))

    def test_unknown_id_config_or_bad_date_exits_before_evaluating(self):
        for argv in (["--ids", "A,NOPE"], ["--config", "best"], ["--cutoff", "28/04/2025"]):
            with self.subTest(argv=argv), patch("sys.stderr"):
                with self.assertRaises(SystemExit):
                    ev.main(["--questions", str(self.questions), *argv])
        self.evaluate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
