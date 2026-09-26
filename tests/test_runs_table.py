"""The saved-runs table's selection handling. Streamlit keeps a dataframe's
selection as ROW INDICES in widget state across reruns; when the run list
changes (a run deleted, or a new one finished — the list is newest first) a
stale index must never crash the page or silently point at a different run."""
import os
import unittest
from datetime import datetime, timezone

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import runs  # noqa: E402
from ui.components import runs_table  # noqa: E402


def _info(run_id):
    return runs.RunInfo(id=run_id, status="done", started=datetime(2026, 1, 1, tzinfo=timezone.utc))


A, B, C = _info("20260103T000000Z_a"), _info("20260102T000000Z_b"), _info("20260101T000000Z_c")


class SelectionTests(unittest.TestCase):
    def test_stale_index_after_a_deletion_is_ignored_not_an_index_error(self):
        # the reported crash: row 2 was selected, then a run was deleted -> 2 rows left
        self.assertIsNone(runs_table.selected_run([A, B], [2]))

    def test_valid_index_returns_that_run(self):
        self.assertEqual(runs_table.selected_run([A, B, C], [1]), B)

    def test_no_selection_is_none(self):
        self.assertIsNone(runs_table.selected_run([A, B], []))

    def test_widget_key_changes_whenever_the_set_of_runs_changes(self):
        # a new key = a fresh widget = no stale selection carried over
        before = runs_table.table_key([B, C])
        self.assertEqual(before, runs_table.table_key([B, C]))           # unchanged list keeps its selection
        self.assertNotEqual(before, runs_table.table_key([A, B, C]))     # a new run shifted every row
        self.assertNotEqual(before, runs_table.table_key([C]))           # a run was deleted


if __name__ == "__main__":
    unittest.main()
