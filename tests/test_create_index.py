"""Deterministic tests for create_index.py — no network, no AWS, no real credentials.

The OpenSearch client is a tiny fake; opensearch_client() itself is patched out so
importing/running this module never touches boto3 or the real collection.
"""
import os
import unittest
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import create_index  # noqa: E402


class FakeIndicesClient:
    """Records calls; never touches a network."""

    def __init__(self, exists=False):
        self._exists = exists
        self.create_calls = []
        self.delete_calls = []

    def exists(self, index):
        return self._exists

    def create(self, index, body):
        self.create_calls.append((index, body))

    def delete(self, index):
        self.delete_calls.append(index)


class FakeOpenSearchClient:
    def __init__(self, exists=False, count=0):
        self.indices = FakeIndicesClient(exists=exists)
        self._count = count
        self.count_calls = []

    def count(self, index):
        self.count_calls.append(index)
        return {"count": self._count}


class IndexBodyTests(unittest.TestCase):
    def test_schema_matches_the_agreed_mapping(self):
        props = create_index.INDEX_BODY["mappings"]["properties"]
        self.assertEqual(props["vector"]["type"], "knn_vector")
        self.assertEqual(props["vector"]["dimension"], create_index.EMBED_DIM)
        self.assertEqual(props["vector"]["method"], {"name": "hnsw", "space_type": "innerproduct"})
        self.assertEqual(props["text"], {"type": "text"})
        self.assertEqual(props["source"], {"type": "keyword"})
        self.assertEqual(props["corpus"], {"type": "keyword"})
        self.assertEqual(props["audience"], {"type": "keyword"})
        self.assertEqual(props["subjects"], {"type": "keyword"})
        self.assertEqual(props["last_updated"], {"type": "date", "format": "yyyy-MM-dd"})
        self.assertTrue(create_index.INDEX_BODY["settings"]["index"]["knn"])


class EnsureIndexTests(unittest.TestCase):
    """ensure_index(client) is the non-destructive lifecycle function main() calls."""

    def test_missing_index_is_created(self):
        client = FakeOpenSearchClient(exists=False)
        create_index.ensure_index(client)
        self.assertEqual(client.indices.create_calls, [(create_index.INDEX_NAME, create_index.INDEX_BODY)])

    def test_existing_index_is_never_deleted(self):
        client = FakeOpenSearchClient(exists=True, count=400)
        create_index.ensure_index(client)
        self.assertEqual(client.indices.delete_calls, [])

    def test_existing_index_is_never_recreated(self):
        client = FakeOpenSearchClient(exists=True, count=400)
        create_index.ensure_index(client)
        self.assertEqual(client.indices.create_calls, [])

    def test_existing_index_reports_its_document_count(self):
        client = FakeOpenSearchClient(exists=True, count=400)
        create_index.ensure_index(client)
        self.assertEqual(client.count_calls, [create_index.INDEX_NAME])

    def test_missing_index_does_not_bother_counting_first(self):
        client = FakeOpenSearchClient(exists=False)
        create_index.ensure_index(client)
        self.assertEqual(client.count_calls, [])


class MainNeverDeletesTests(unittest.TestCase):
    """main() must never call indices.delete, on either branch."""

    @patch("create_index.opensearch_client")
    def test_main_on_missing_index(self, fake_opensearch_client):
        client = FakeOpenSearchClient(exists=False)
        fake_opensearch_client.return_value = client
        create_index.main()
        self.assertEqual(client.indices.create_calls, [(create_index.INDEX_NAME, create_index.INDEX_BODY)])
        self.assertEqual(client.indices.delete_calls, [])

    @patch("create_index.opensearch_client")
    def test_main_on_existing_index(self, fake_opensearch_client):
        client = FakeOpenSearchClient(exists=True, count=400)
        fake_opensearch_client.return_value = client
        create_index.main()
        self.assertEqual(client.indices.create_calls, [])
        self.assertEqual(client.indices.delete_calls, [])


if __name__ == "__main__":
    unittest.main()
