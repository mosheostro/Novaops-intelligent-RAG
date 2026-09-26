"""runs.py — saved-run storage and the eval.py subprocess launcher. Popen is
mocked; no evaluation ever actually runs."""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import models  # noqa: E402
import runs  # noqa: E402

RESULT = models.EvaluationResult(
    metadata=models.EvaluationMetadata(
        question_count=0, configs=list(models.CONFIG_NAMES), candidate_pool_size=10,
        static_top_k=3, dynamic_threshold=0.6, baseline_top_k=4,
    ),
    questions={},
    summary={},
)

SUBSET_RESULT = RESULT.model_copy(update={
    "metadata": RESULT.metadata.model_copy(update={
        "question_count": 2, "configs": ["baseline", "filter + rerank dynamic"], "cutoff": date(2025, 4, 28),
    }),
    "questions": {qid: models.QuestionResult(
        id=qid, question="q?", audience="employee", expect_refusal=False, key_facts=[],
        planned_subjects=None, configurations={},
    ) for qid in ("A", "B")},
})


def _proc(returncode=None):
    p = MagicMock()
    p.poll.return_value = returncode
    return p


class RunsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        patch.object(runs, "RUNS_DIR", self.dir).start()
        patch.dict(runs._procs, clear=True).start()
        self.popen = patch("runs.subprocess.Popen", return_value=_proc()).start()
        self.addCleanup(patch.stopall)

    def _save(self, run_id, result=RESULT):
        (self.dir / f"{run_id}.json").write_text(result.model_dump_json(), encoding="utf-8")

    def test_list_runs_is_empty_when_directory_missing(self):
        with patch.object(runs, "RUNS_DIR", self.dir / "nope"):
            self.assertEqual(runs.list_runs(), [])

    def test_saved_json_is_listed_as_done_newest_first_and_loads(self):
        self._save("20260101T000000Z_eval_questions")
        self._save("20260102T000000Z_eval_questions")
        listed = runs.list_runs()
        self.assertEqual([r.id for r in listed],
                         ["20260102T000000Z_eval_questions", "20260101T000000Z_eval_questions"])
        self.assertEqual(listed[0].status, "done")
        self.assertEqual(listed[0].started.year, 2026)
        self.assertEqual(runs.load_run(listed[0].id), RESULT)

    def test_listing_describes_a_finished_run_from_its_saved_metadata(self):
        self._save("20260101T000000Z_eval_questions", SUBSET_RESULT)
        [info] = runs.list_runs()
        self.assertEqual(info.question_ids, ("A", "B"))
        self.assertEqual(info.configs, ("baseline", "filter + rerank dynamic"))
        self.assertEqual(info.cutoff, date(2025, 4, 28))

    def test_launch_spawns_eval_with_the_selected_experiment(self):
        run_id = runs.launch_run(["SEV_3YR", "ACCESS_REVIEW"], ["baseline", "filter + rerank dynamic"],
                                 cutoff=date(2025, 4, 28))
        cmd = self.popen.call_args.args[0]
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith("eval.py"))
        self.assertEqual(cmd[2:], ["--ids", "SEV_3YR,ACCESS_REVIEW",
                                   "--config", "baseline", "--config", "filter + rerank dynamic",
                                   "--cutoff", "2025-04-28", "--save", "--run-id", run_id])
        self.assertTrue(run_id.endswith("_eval_questions"))
        self.assertTrue((self.dir / f"{run_id}.log").is_file())
        self.assertEqual(runs.run_status(run_id), "running")
        [info] = runs.list_runs()
        self.assertEqual((info.id, info.question_ids, info.configs), (run_id, None, None))  # unknown until saved

    def test_launch_without_cutoff_passes_no_cutoff_flag(self):
        runs.launch_run(["A"], ["baseline"])
        self.assertNotIn("--cutoff", self.popen.call_args.args[0])

    def test_launch_requires_at_least_one_question_and_one_config(self):
        with self.assertRaises(ValueError):
            runs.launch_run([], ["baseline"])
        with self.assertRaises(ValueError):
            runs.launch_run(["A"], [])
        self.popen.assert_not_called()

    def test_second_launch_is_refused_while_one_is_running(self):
        runs.launch_run(["A"], ["baseline"])
        with self.assertRaises(runs.RunAlreadyActiveError):
            runs.launch_run(["B"], ["baseline"])
        self.assertEqual(self.popen.call_count, 1)

    def test_finished_process_with_json_is_done_and_frees_the_lock(self):
        run_id = runs.launch_run(["A"], ["baseline"])
        runs._procs[run_id].poll.return_value = 0
        self._save(run_id)
        self.assertEqual(runs.run_status(run_id), "done")
        self.assertIsNone(runs.active_run())

    def test_finished_process_without_json_is_failed(self):
        run_id = runs.launch_run(["A"], ["baseline"])
        runs._procs[run_id].poll.return_value = 1
        self.assertEqual(runs.run_status(run_id), "failed")

    def test_delete_removes_only_that_runs_artifacts(self):
        self._save("20260101T000000Z_eval_questions")
        (self.dir / "20260101T000000Z_eval_questions.log").write_text("log", encoding="utf-8")
        self._save("20260102T000000Z_eval_questions")
        runs.delete_run("20260101T000000Z_eval_questions")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["20260102T000000Z_eval_questions.json"])
        self.assertEqual([r.id for r in runs.list_runs()], ["20260102T000000Z_eval_questions"])

    def test_delete_of_a_failed_run_removes_its_log(self):
        (self.dir / "R_failed.log").write_text("boom", encoding="utf-8")
        runs.delete_run("R_failed")
        self.assertEqual(runs.list_runs(), [])

    def test_delete_refuses_a_running_run(self):
        run_id = runs.launch_run(["A"], ["baseline"])
        with self.assertRaises(runs.RunAlreadyActiveError):
            runs.delete_run(run_id)
        self.assertTrue((self.dir / f"{run_id}.log").exists())

    def test_delete_accepts_only_listed_run_ids(self):
        outside = self.dir.parent / "victim.json"
        for bad in ("nope", "../victim", str(outside.with_suffix(""))):
            with self.subTest(run_id=bad), self.assertRaises(FileNotFoundError):
                runs.delete_run(bad)

    def test_log_tail_returns_last_lines(self):
        (self.dir / "R.log").write_text("\n".join(f"line {i}" for i in range(50)), encoding="utf-8")
        self.assertEqual(runs.log_tail("R", 3), "line 47\nline 48\nline 49")
        self.assertEqual(runs.log_tail("missing"), "")


if __name__ == "__main__":
    unittest.main()
