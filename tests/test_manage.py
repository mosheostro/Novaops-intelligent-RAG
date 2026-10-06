"""Deterministic tests for manage.py — no network, no AWS, no real credentials.

The control-plane (aoss) client is a tiny fake injected into get_collection() /
status() / down(); the data-plane check inside status() goes through client.py,
so client.opensearch_client is patched there. input() and time.sleep() are
patched so nothing blocks and nothing really waits.
"""
import io
import logging
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from botocore.exceptions import ClientError  # noqa: E402

import manage  # noqa: E402
from client import INDEX_NAME  # noqa: E402


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


def _data_plane(index_exists=True, count=400):
    os_client = Mock()
    os_client.indices.exists.return_value = index_exists
    os_client.count.return_value = {"count": count}
    return os_client


class CollectionHealthTests(unittest.TestCase):
    """The structured health use case behind `status` — returns data, prints nothing."""

    def _health(self, aoss):
        result, output = _run(manage.collection_health, aoss)
        self.assertEqual(output, "")  # never prints, whatever the outcome
        return result

    def test_missing_collection(self):
        self.assertEqual(self._health(FakeAossClient(collection=None)),
                         manage.CollectionHealth(status=None, endpoint=None, index_exists=None,
                                                 chunk_count=None, data_plane_error=None))

    @patch("client.opensearch_client")
    def test_non_active_collection_skips_the_data_plane(self, fake_opensearch_client):
        health = self._health(FakeAossClient(collection=CREATING_COLLECTION))
        fake_opensearch_client.assert_not_called()
        self.assertEqual(health, manage.CollectionHealth(status="CREATING", endpoint=None, index_exists=None,
                                                         chunk_count=None, data_plane_error=None))

    @patch("client.opensearch_client")
    def test_active_collection_with_index_and_chunks(self, fake_opensearch_client):
        fake_opensearch_client.return_value = _data_plane(index_exists=True, count=400)
        self.assertEqual(self._health(FakeAossClient(collection=ACTIVE_COLLECTION)),
                         manage.CollectionHealth(status="ACTIVE", endpoint=ACTIVE_COLLECTION["collectionEndpoint"],
                                                 index_exists=True, chunk_count=400, data_plane_error=None))

    @patch("client.opensearch_client")
    def test_active_collection_with_missing_index(self, fake_opensearch_client):
        os_client = _data_plane(index_exists=False)
        fake_opensearch_client.return_value = os_client
        health = self._health(FakeAossClient(collection=ACTIVE_COLLECTION))
        os_client.count.assert_not_called()
        self.assertEqual((health.status, health.index_exists, health.chunk_count, health.data_plane_error),
                         ("ACTIVE", False, None, None))

    @patch("client.opensearch_client")
    def test_data_plane_failure_is_recorded_not_raised(self, fake_opensearch_client):
        fake_opensearch_client.side_effect = RuntimeError("boom: cold start timeout")
        health = self._health(FakeAossClient(collection=ACTIVE_COLLECTION))
        self.assertEqual((health.status, health.index_exists, health.chunk_count, health.data_plane_error),
                         ("ACTIVE", None, None, "boom: cold start timeout"))

    @patch("client.opensearch_client")
    def test_data_plane_system_exit_does_not_terminate(self, fake_opensearch_client):
        # client.resolve_endpoint signals a missing/inactive collection with SystemExit.
        fake_opensearch_client.side_effect = SystemExit("Collection 'x' is CREATING — wait for ACTIVE.")
        health = self._health(FakeAossClient(collection=ACTIVE_COLLECTION))
        self.assertEqual(health.data_plane_error, "Collection 'x' is CREATING — wait for ACTIVE.")
        self.assertIsNone(health.index_exists)

    def test_control_plane_failure_propagates(self):
        aoss = Mock()
        aoss.batch_get_collection.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "BatchGetCollection")
        with self.assertRaises(ClientError):
            manage.collection_health(aoss)


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


PRIVATE_NAME = "SECRET-COLLECTION-7f3a"
PRIVATE_ENDPOINT = "https://SECRET-abc123.us-east-1.aoss.amazonaws.com"
PRIVATE_ERROR = f"ConnectionError to {PRIVATE_ENDPOINT} for account 123456789012"


class CollectionHealthLoggingTests(unittest.TestCase):
    """collection_health's logs reach whatever runs it — including an MCP client
    reading the server's stderr — so they carry states and exception types only:
    no collection name, endpoint, index name, account id or raw exception text."""

    def setUp(self):
        self.capture = _Capture()
        log = logging.getLogger("manage")
        self._level = log.level
        log.setLevel(logging.DEBUG)
        log.addHandler(self.capture)
        self.addCleanup(log.removeHandler, self.capture)
        self.addCleanup(log.setLevel, self._level)
        patch.object(manage, "NAME", PRIVATE_NAME).start()
        self.opensearch_client = patch("client.opensearch_client").start()
        self.addCleanup(patch.stopall)

    def _logged(self, collection) -> str:
        with redirect_stdout(io.StringIO()):
            manage.collection_health(FakeAossClient(collection=collection))
        return "\n".join(r.getMessage() for r in self.capture.records)

    def assertNoPrivateValues(self, text):
        for private in (PRIVATE_NAME, "SECRET", PRIVATE_ENDPOINT, "aoss", "amazonaws", "us-east-1", INDEX_NAME,
                        "123456789012", "ConnectionError to"):
            self.assertNotIn(private, text)

    def test_active_collection_with_index_logs_state_and_count_only(self):
        os_client = _data_plane(index_exists=True, count=400)
        self.opensearch_client.return_value = os_client
        logged = self._logged(dict(ACTIVE_COLLECTION, collectionEndpoint=PRIVATE_ENDPOINT))
        self.assertIn("ACTIVE", logged)
        self.assertIn("400", logged)
        self.assertNoPrivateValues(logged)

    def test_non_active_collection_logs_state_only(self):
        logged = self._logged(dict(CREATING_COLLECTION, collectionEndpoint=PRIVATE_ENDPOINT))
        self.assertIn("CREATING", logged)
        self.assertNoPrivateValues(logged)

    def test_data_plane_failure_logs_the_exception_type_not_its_text(self):
        for exc in (RuntimeError(PRIVATE_ERROR), SystemExit(f"Collection '{PRIVATE_NAME}' not found")):
            with self.subTest(exc=type(exc).__name__):
                self.capture.records.clear()
                self.opensearch_client.side_effect = exc
                logged = self._logged(dict(ACTIVE_COLLECTION, collectionEndpoint=PRIVATE_ENDPOINT))
                warnings = [r for r in self.capture.records if r.levelno == logging.WARNING]
                self.assertEqual(len(warnings), 1)
                self.assertIn("data plane", warnings[0].getMessage())
                self.assertIn(type(exc).__name__, warnings[0].getMessage())
                self.assertNoPrivateValues(logged)

    def test_missing_collection_logs_nothing_private(self):
        self.assertNoPrivateValues(self._logged(None))


class StatusOutputTests(unittest.TestCase):
    """`status` prints exactly what it printed before collection_health existed."""

    def _status(self, collection):
        return _run(manage.status, FakeAossClient(collection=collection))[1]

    def test_missing(self):
        self.assertEqual(self._status(None), f"Collection '{manage.NAME}': does NOT exist.\n")

    @patch("client.opensearch_client")
    def test_not_active(self, _fake_opensearch_client):
        self.assertEqual(self._status(CREATING_COLLECTION),
                         f"Collection '{manage.NAME}': CREATING\n  endpoint: (pending)\n")

    @patch("client.opensearch_client")
    def test_active_with_index(self, fake_opensearch_client):
        fake_opensearch_client.return_value = _data_plane(index_exists=True, count=400)
        self.assertEqual(self._status(ACTIVE_COLLECTION),
                         f"Collection '{manage.NAME}': ACTIVE\n"
                         f"  endpoint: {ACTIVE_COLLECTION['collectionEndpoint']}\n"
                         f"  index '{INDEX_NAME}': 400 chunks indexed\n")

    @patch("client.opensearch_client")
    def test_active_without_index(self, fake_opensearch_client):
        fake_opensearch_client.return_value = _data_plane(index_exists=False)
        self.assertEqual(self._status(ACTIVE_COLLECTION),
                         f"Collection '{manage.NAME}': ACTIVE\n"
                         f"  endpoint: {ACTIVE_COLLECTION['collectionEndpoint']}\n"
                         f"  index '{INDEX_NAME}': not created yet — run create_index.py\n")

    @patch("client.opensearch_client")
    def test_active_with_data_plane_failure(self, fake_opensearch_client):
        fake_opensearch_client.side_effect = RuntimeError("boom")
        self.assertEqual(self._status(ACTIVE_COLLECTION),
                         f"Collection '{manage.NAME}': ACTIVE\n"
                         f"  endpoint: {ACTIVE_COLLECTION['collectionEndpoint']}\n"
                         f"  (couldn't reach the data plane yet: boom)\n")


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
