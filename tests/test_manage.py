"""Deterministic tests for manage.py — no network, no AWS, no real credentials.

The control-plane (aoss) client is a tiny fake injected into get_collection() /
status() / down(); the data-plane check inside status() goes through client.py,
so client.opensearch_client is patched there. input() and time.sleep() are
patched so nothing blocks and nothing really waits.
"""
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import manage  # noqa: E402


class FakeAossClient:
    """A control-plane fake. `collection` is the dict batch_get_collection would
    return (or None if it doesn't exist yet). delete_collection() removes it and
    records the call; a later batch_get_collection then reports it gone."""

    def __init__(self, collection=None):
        self._collection = collection
        self.delete_calls = []

    def batch_get_collection(self, names):
        assert names == [manage.NAME]
        details = [self._collection] if self._collection else []
        return {"collectionDetails": details}

    def delete_collection(self, id):
        self.delete_calls.append(id)
        self._collection = None


ACTIVE_COLLECTION = {"id": "abc123", "status": "ACTIVE", "collectionEndpoint": "https://abc123.aoss.example"}
CREATING_COLLECTION = {"id": "def456", "status": "CREATING"}


def _run(func, *args):
    """Capture stdout for a call, return (result, printed_text)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        result = func(*args)
    return result, buf.getvalue()


class GetCollectionTests(unittest.TestCase):
    def test_returns_the_collection_when_present(self):
        aoss = FakeAossClient(collection=ACTIVE_COLLECTION)
        self.assertEqual(manage.get_collection(aoss), ACTIVE_COLLECTION)

    def test_returns_none_when_absent(self):
        aoss = FakeAossClient(collection=None)
        self.assertIsNone(manage.get_collection(aoss))


class StatusTests(unittest.TestCase):
    def test_reports_a_missing_collection(self):
        aoss = FakeAossClient(collection=None)
        _, output = _run(manage.status, aoss)
        self.assertIn(manage.NAME, output)
        self.assertIn("does NOT exist", output)

    @patch("client.opensearch_client")
    def test_reports_an_existing_collection_status_and_endpoint(self, fake_opensearch_client):
        fake_opensearch_client.side_effect = RuntimeError("data plane unreachable in this test")
        aoss = FakeAossClient(collection=CREATING_COLLECTION)
        _, output = _run(manage.status, aoss)
        self.assertIn("CREATING", output)

    @patch("client.opensearch_client")
    def test_reports_index_count_when_active_and_index_exists(self, fake_opensearch_client):
        os_client = Mock()
        os_client.indices.exists.return_value = True
        os_client.count.return_value = {"count": 400}
        fake_opensearch_client.return_value = os_client
        aoss = FakeAossClient(collection=ACTIVE_COLLECTION)
        _, output = _run(manage.status, aoss)
        self.assertIn("ACTIVE", output)
        self.assertIn(ACTIVE_COLLECTION["collectionEndpoint"], output)
        self.assertIn("400", output)

    @patch("client.opensearch_client")
    def test_reports_index_not_created_when_active_but_index_missing(self, fake_opensearch_client):
        os_client = Mock()
        os_client.indices.exists.return_value = False
        fake_opensearch_client.return_value = os_client
        aoss = FakeAossClient(collection=ACTIVE_COLLECTION)
        _, output = _run(manage.status, aoss)
        self.assertIn("not created", output.lower())

    @patch("client.opensearch_client")
    def test_data_plane_exception_does_not_crash_status(self, fake_opensearch_client):
        fake_opensearch_client.side_effect = RuntimeError("boom: cold start timeout")
        aoss = FakeAossClient(collection=ACTIVE_COLLECTION)
        # Must not raise -- a data-plane failure is best-effort/reported, not fatal.
        _, output = _run(manage.status, aoss)
        self.assertIn("ACTIVE", output)
        self.assertIn("boom", output)


class DownTests(unittest.TestCase):
    def test_missing_collection_does_not_ask_or_delete(self):
        aoss = FakeAossClient(collection=None)
        with patch("builtins.input") as fake_input:
            _, output = _run(manage.down, aoss)
        fake_input.assert_not_called()
        self.assertEqual(aoss.delete_calls, [])
        self.assertIn("nothing to delete", output.lower())

    @patch("time.sleep")
    def test_exact_remove_confirms_and_deletes(self, _sleep):
        aoss = FakeAossClient(collection=dict(ACTIVE_COLLECTION))
        with patch("builtins.input", return_value="REMOVE"):
            manage.down(aoss)
        self.assertEqual(aoss.delete_calls, [ACTIVE_COLLECTION["id"]])

    @patch("time.sleep")
    def test_empty_input_cancels(self, _sleep):
        aoss = FakeAossClient(collection=dict(ACTIVE_COLLECTION))
        with patch("builtins.input", return_value=""):
            manage.down(aoss)
        self.assertEqual(aoss.delete_calls, [])

    @patch("time.sleep")
    def test_yes_variant_lowercase_y_cancels(self, _sleep):
        aoss = FakeAossClient(collection=dict(ACTIVE_COLLECTION))
        with patch("builtins.input", return_value="y"):
            manage.down(aoss)
        self.assertEqual(aoss.delete_calls, [])

    @patch("time.sleep")
    def test_lowercase_remove_cancels(self, _sleep):
        # Only the EXACT string "REMOVE" authorizes deletion.
        aoss = FakeAossClient(collection=dict(ACTIVE_COLLECTION))
        with patch("builtins.input", return_value="remove"):
            manage.down(aoss)
        self.assertEqual(aoss.delete_calls, [])

    @patch("time.sleep")
    def test_other_inputs_all_cancel(self, _sleep):
        for bad in ("yes", "Y", "YES", "REMOVE ", " REMOVE", "sure", "1"):
            with self.subTest(bad=bad):
                aoss = FakeAossClient(collection=dict(ACTIVE_COLLECTION))
                with patch("builtins.input", return_value=bad):
                    manage.down(aoss)
                self.assertEqual(aoss.delete_calls, [])

    @patch("time.sleep")
    def test_confirmation_happens_before_delete_is_called(self, _sleep):
        order = []
        aoss = FakeAossClient(collection=dict(ACTIVE_COLLECTION))

        real_delete = aoss.delete_collection

        def tracking_delete(id):
            order.append("delete")
            return real_delete(id)

        aoss.delete_collection = tracking_delete

        def tracking_input(prompt):
            order.append("input")
            return "REMOVE"

        with patch("builtins.input", side_effect=tracking_input):
            manage.down(aoss)
        self.assertEqual(order, ["input", "delete"])

    def test_down_never_recreates_or_adds_a_force_bypass(self):
        # No 'up' path and no undocumented bypass flag are exposed as commands.
        self.assertEqual(set(manage.COMMANDS), {"status", "down"})


if __name__ == "__main__":
    unittest.main()
