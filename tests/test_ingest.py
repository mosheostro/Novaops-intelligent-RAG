"""Deterministic tests for ingest.py — no network, no AWS, no real credentials.

embed_text, opensearch_client, load_or_tag and opensearchpy.helpers.bulk are all
stubbed or patched. Nothing here talks to Bedrock, OpenSearch, or the real data/.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import ingest  # noqa: E402


class ParseFrontmatterTests(unittest.TestCase):
    def test_extracts_metadata_fields(self):
        text = (
            "---\n"
            "last_updated: 2024-01-29\n"
            "corpus: handbook\n"
            "audience: all\n"
            "---\n"
            "# Severance\n\nBody text here.\n"
        )
        meta, body = ingest.parse_frontmatter(text)
        self.assertEqual(meta, {"last_updated": "2024-01-29", "corpus": "handbook", "audience": "all"})

    def test_body_has_no_frontmatter_fence_or_fields(self):
        text = "---\nlast_updated: 2024-01-29\naudience: all\n---\n# Title\n\nBody.\n"
        _meta, body = ingest.parse_frontmatter(text)
        self.assertFalse(body.startswith("---"))
        self.assertNotIn("---", body)
        self.assertIn("# Title", body)
        self.assertIn("Body.", body)

    def test_text_without_frontmatter_is_returned_unchanged(self):
        text = "# No frontmatter here.\n\nJust body text.\n"
        meta, body = ingest.parse_frontmatter(text)
        self.assertEqual(meta, {})
        self.assertEqual(body, text)


class ChunkDocumentTests(unittest.TestCase):
    def _words(self, n):
        return " ".join(f"w{i}" for i in range(n))

    def test_chunk_size_is_250_words(self):
        chunks = ingest.chunk_document(self._words(250))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0].split()), 250)

    def test_long_document_splits_with_250_word_chunks(self):
        text = self._words(300)
        chunks = ingest.chunk_document(text)
        self.assertEqual(len(chunks[0].split()), 250)

    def test_overlap_is_50_words_between_consecutive_chunks(self):
        text = self._words(300)
        chunks = ingest.chunk_document(text)
        self.assertGreaterEqual(len(chunks), 2)
        first_words = chunks[0].split()
        second_words = chunks[1].split()
        # The step is CHUNK_WORDS - OVERLAP_WORDS = 200, so the second chunk's
        # first 50 words must equal the first chunk's last 50 words.
        self.assertEqual(first_words[-50:], second_words[:50])

    def test_constants_are_250_and_50(self):
        self.assertEqual(ingest.CHUNK_WORDS, 250)
        self.assertEqual(ingest.OVERLAP_WORDS, 50)


class BuildRecordsTests(unittest.TestCase):
    def test_metadata_propagates_to_every_chunk(self):
        documents = [{
            "key": "handbook/severance.md", "corpus": "handbook", "audience": "all",
            "last_updated": "2024-01-29", "source": "severance.md",
            "text": " ".join(f"w{i}" for i in range(300)),
        }]
        tags = {"handbook/severance.md": ["severance_and_termination"]}
        records = ingest.build_records(documents, tags)
        self.assertGreaterEqual(len(records), 2)
        for rec in records:
            self.assertEqual(rec["corpus"], "handbook")
            self.assertEqual(rec["audience"], "all")
            self.assertEqual(rec["last_updated"], "2024-01-29")
            self.assertEqual(rec["source"], "severance.md")

    def test_subject_tags_propagate_to_every_chunk(self):
        documents = [{
            "key": "manager_playbook/hiring.md", "corpus": "manager_playbook", "audience": "manager",
            "last_updated": "2024-06-01", "source": "hiring.md",
            "text": " ".join(f"w{i}" for i in range(300)),
        }]
        tags = {"manager_playbook/hiring.md": ["hiring_and_onboarding", "managing_people"]}
        records = ingest.build_records(documents, tags)
        for rec in records:
            self.assertEqual(rec["subjects"], ["hiring_and_onboarding", "managing_people"])

    def test_chunk_text_never_contains_the_frontmatter_fence(self):
        documents = [{
            "key": "handbook/x.md", "corpus": "handbook", "audience": "all",
            "last_updated": "2024-01-01", "source": "x.md",
            "text": " ".join(f"w{i}" for i in range(300)),
        }]
        records = ingest.build_records(documents, {"handbook/x.md": []})
        for rec in records:
            self.assertNotIn("---", rec["text"])

    def test_one_record_per_chunk_across_multiple_documents(self):
        documents = [
            {"key": "a.md", "corpus": "handbook", "audience": "all", "last_updated": "2024-01-01",
             "source": "a.md", "text": " ".join(f"w{i}" for i in range(250))},
            {"key": "b.md", "corpus": "manager_playbook", "audience": "manager", "last_updated": "2024-01-01",
             "source": "b.md", "text": " ".join(f"w{i}" for i in range(300))},
        ]
        tags = {"a.md": [], "b.md": ["managing_people"]}
        records = ingest.build_records(documents, tags)
        expected = len(ingest.chunk_document(documents[0]["text"])) + len(ingest.chunk_document(documents[1]["text"]))
        self.assertEqual(len(records), expected)


class LoadDocumentsWithMetadataTests(unittest.TestCase):
    def test_default_data_dir_is_the_project_level_data_folder(self):
        # The canonical corpus lives at SDD/data/, a sibling of ingest.py -- not
        # reference/ and not a parent-level lesson layout.
        self.assertEqual(ingest.DATA_DIR, Path(ingest.__file__).resolve().parent / "data")

    def test_reads_both_corpus_directories_and_their_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            handbook = data_dir / "handbook"
            manager = data_dir / "manager_playbook"
            handbook.mkdir()
            manager.mkdir()
            (handbook / "severance.md").write_text(
                "---\nlast_updated: 2024-01-29\ncorpus: handbook\naudience: all\n---\n"
                "# Severance\n\nBody.\n", encoding="utf-8",
            )
            (manager / "hiring.md").write_text(
                "---\nlast_updated: 2024-06-01\ncorpus: manager_playbook\naudience: manager\n---\n"
                "# Hiring\n\nBody.\n", encoding="utf-8",
            )
            with patch.object(ingest, "DATA_DIR", data_dir):
                documents = ingest.load_documents_with_metadata()

            by_source = {d["source"]: d for d in documents}
            self.assertEqual(set(by_source), {"severance.md", "hiring.md"})
            self.assertEqual(by_source["severance.md"]["corpus"], "handbook")
            self.assertEqual(by_source["severance.md"]["audience"], "all")
            self.assertEqual(by_source["severance.md"]["last_updated"], "2024-01-29")
            self.assertEqual(by_source["hiring.md"]["corpus"], "manager_playbook")
            self.assertEqual(by_source["hiring.md"]["audience"], "manager")
            self.assertEqual(by_source["hiring.md"]["last_updated"], "2024-06-01")
            self.assertNotIn("---", by_source["severance.md"]["text"])


class FakeIndicesClient:
    def __init__(self, exists):
        self._exists = exists

    def exists(self, index):
        return self._exists


class FakeGuardClient:
    """A client for exercising ensure_index_ready_for_ingest(): reports whether
    the index exists and, if so, how many documents it holds."""

    def __init__(self, exists, count=0):
        self.indices = FakeIndicesClient(exists=exists)
        self._count = count
        self.count_calls = 0

    def count(self, index):
        self.count_calls += 1
        return {"count": self._count}


class EnsureIndexReadyForIngestTests(unittest.TestCase):
    """The populated-index guard: must run BEFORE tagging/embedding/bulk."""

    def test_missing_index_refuses_and_names_create_index(self):
        client = FakeGuardClient(exists=False)
        with self.assertRaises(SystemExit) as ctx:
            ingest.ensure_index_ready_for_ingest(client)
        self.assertIn("create_index.py", str(ctx.exception))

    def test_empty_existing_index_is_allowed(self):
        client = FakeGuardClient(exists=True, count=0)
        ingest.ensure_index_ready_for_ingest(client)  # must not raise

    def test_nonempty_index_is_refused(self):
        client = FakeGuardClient(exists=True, count=400)
        with self.assertRaises(SystemExit) as ctx:
            ingest.ensure_index_ready_for_ingest(client)
        self.assertIn("400", str(ctx.exception))

    @patch("ingest.load_or_tag")
    @patch("ingest.embed_text")
    @patch("ingest.helpers")
    def test_nonempty_index_skips_tagging_embedding_and_bulk(self, fake_helpers, fake_embed, fake_load_or_tag):
        client = FakeGuardClient(exists=True, count=400)
        with self.assertRaises(SystemExit):
            ingest.ensure_index_ready_for_ingest(client)
        fake_load_or_tag.assert_not_called()
        fake_embed.assert_not_called()
        fake_helpers.bulk.assert_not_called()

    def test_main_stops_before_any_ingestion_work_when_index_is_populated(self):
        # main() must call the guard before load_or_tag/embed_records/index_records,
        # using the SAME client it just opened.
        client = FakeGuardClient(exists=True, count=400)
        with patch("ingest.opensearch_client", return_value=client), \
             patch("ingest.load_documents_with_metadata") as fake_load_docs, \
             patch("ingest.load_or_tag") as fake_load_or_tag, \
             patch("ingest.embed_records") as fake_embed_records, \
             patch("ingest.index_records") as fake_index_records:
            with self.assertRaises(SystemExit):
                ingest.main()
        fake_load_docs.assert_not_called()
        fake_load_or_tag.assert_not_called()
        fake_embed_records.assert_not_called()
        fake_index_records.assert_not_called()


class FakeOpenSearchClient:
    """count() returns `expected` immediately so wait_until_indexed never sleeps."""

    def __init__(self, expected):
        self._expected = expected
        self.count_calls = 0

    def count(self, index):
        self.count_calls += 1
        return {"count": self._expected}


class IndexRecordsTests(unittest.TestCase):
    @patch("ingest.helpers")
    def test_bulk_actions_have_index_and_source_but_no_id(self, fake_helpers):
        records = [
            {"text": "chunk one", "source": "a.md", "corpus": "handbook", "audience": "all",
             "subjects": [], "last_updated": "2024-01-01", "vector": [0.1, 0.2]},
            {"text": "chunk two", "source": "b.md", "corpus": "manager_playbook", "audience": "manager",
             "subjects": ["managing_people"], "last_updated": "2024-01-01", "vector": [0.3, 0.4]},
        ]
        client = FakeOpenSearchClient(expected=len(records))
        ingest.index_records(client, records)

        fake_helpers.bulk.assert_called_once()
        (bulk_client, actions), _kwargs = fake_helpers.bulk.call_args
        self.assertIs(bulk_client, client)
        self.assertEqual(len(actions), 2)
        for action, record in zip(actions, records):
            self.assertEqual(action["_index"], ingest.INDEX_NAME)
            self.assertEqual(action["_source"], record)
            self.assertNotIn("_id", action)


if __name__ == "__main__":
    unittest.main()
