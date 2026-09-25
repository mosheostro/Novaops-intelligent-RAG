"""Behavioral logging tests for the evaluation pipeline (eval.py) — kept
separate from the already-large tests/test_eval.py, per project convention.

These test WHAT gets logged and at WHICH level for a handful of important
boundaries (lifecycle, the two WARNING conditions, the security ERROR, and
the top-level exception boundary) — not every DEBUG statement. Uses
`unittest.TestCase.assertLogs`, the stdlib tool built for exactly this, so no
test here touches the real root logger's handlers or the real `logs/`
directory. `eval.configure_logging` is patched wherever `eval.main()` is
called directly, so no test ever triggers real file/console handler setup.
"""
import os
import unittest
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import eval as ev  # noqa: E402
import models  # noqa: E402

CLIENT = object()


def _hit(text, score, audience="all", subjects=None, source="doc.md",
         corpus="handbook", last_updated="2024-01-01"):
    return {"_score": score, "_source": {
        "text": text, "source": source, "corpus": corpus,
        "audience": audience, "subjects": subjects or [], "last_updated": last_updated,
    }}


def _q(id="Q1", question="how much severance do I get?", audience="employee",
       expect_refusal=False, key_facts=None, report=False):
    return {"id": id, "question": question, "audience": audience,
            "expect_refusal": expect_refusal, "key_facts": key_facts or ["fact one"],
            "report": report}


BASELINE_HITS = [_hit(f"base-{i}", 1.0 - i * 0.1) for i in range(4)]
FILTER_HITS = [_hit(f"filt-{i}", 1.0 - i * 0.1) for i in range(4)]
RERANK_ONLY_POOL = [_hit(f"ro-{i}", 1.0 - i * 0.05) for i in range(10)]
FR_POOL = [_hit(f"fr-{i}", 1.0 - i * 0.05) for i in range(10)]
RO_SCORES = [0.1, 0.9, 0.3, 0.8, 0.2, 0.95, 0.05, 0.15, 0.25, 0.35]
FR_SCORES = [0.95, 0.85, 0.75, 0.65, 0.4, 0.3, 0.2, 0.1, 0.05, 0.0]  # 4 clear 0.6


def _standard_knn(client, query, audience, subjects=None, top_k=4, updated_after=None):
    if top_k == ev.BASELINE_TOP_K:
        return BASELINE_HITS if subjects is None else FILTER_HITS
    return RERANK_ONLY_POOL if subjects is None else FR_POOL


def _standard_rerank(query, candidates):
    scores = RO_SCORES if candidates[0]["text"].startswith("ro-") else FR_SCORES
    return sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)


class EvaluationLifecycleLoggingTests(unittest.TestCase):
    def test_evaluate_logs_the_expected_lifecycle_markers(self):
        q = _q(id="LIFECYCLE_Q")
        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", side_effect=_standard_knn), \
             patch("eval.rerank_all", side_effect=_standard_rerank), \
             patch("eval.answer", return_value="the answer"), \
             patch("eval.faithfulness", return_value=(0.8, "ok")), \
             patch("eval.context_relevance", return_value=(0.7, "ok")), \
             patch("eval.completeness", return_value=(0.9, "ok")), \
             patch("eval.refused", return_value=False), \
             self.assertLogs("eval", level="INFO") as cm:
            ev.evaluate(CLIENT, [q])
        joined = "\n".join(cm.output)
        self.assertIn("evaluation started", joined)
        self.assertIn("question=LIFECYCLE_Q started", joined)
        for name in models.CONFIG_NAMES:
            self.assertIn(f"question=LIFECYCLE_Q config={name} completed", joined)
        self.assertIn("question=LIFECYCLE_Q completed", joined)
        self.assertIn("evaluation completed", joined)
        # ~5 config lines + start/end for one question + 2 run-level lines --
        # concise, not a second detailed report.
        self.assertLessEqual(len(cm.output), 12)


class RefusalWarningTests(unittest.TestCase):
    def test_warns_when_expected_refusal_did_not_refuse(self):
        q = _q(id="REFUSAL_Q", expect_refusal=True, question="what was the AWS bill?")
        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", return_value=BASELINE_HITS), \
             patch("eval.rerank_all", side_effect=lambda q_, cands: [(c, 0.5) for c in cands]), \
             patch("eval.answer", return_value="Here is the AWS bill: $42,000."), \
             patch("eval.faithfulness"), patch("eval.context_relevance"), patch("eval.completeness"), \
             patch("eval.refused", return_value=False), \
             self.assertLogs("eval", level="WARNING") as cm:
            ev.evaluate_question(CLIENT, q)
        joined = "\n".join(cm.output)
        self.assertIn("expected a refusal but the answer did not refuse", joined)


class NotFoundWarningTests(unittest.TestCase):
    def test_warns_when_answerable_question_gets_not_found(self):
        q = _q(id="ANSWERABLE_Q", expect_refusal=False)
        low_fr_scores = [0.1] * 10  # every candidate below the 0.6 dynamic threshold

        def rerank(query, candidates):
            scores = RO_SCORES if candidates[0]["text"].startswith("ro-") else low_fr_scores
            return sorted(zip(candidates, scores), key=lambda p: p[1], reverse=True)

        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", side_effect=_standard_knn), \
             patch("eval.rerank_all", side_effect=rerank), \
             patch("eval.answer", return_value="not found in context"), \
             patch("eval.faithfulness", return_value=(0.1, "ok")), \
             patch("eval.context_relevance", return_value=(0.1, "ok")), \
             patch("eval.completeness", return_value=(0.0, "ok")), \
             patch("eval.refused", return_value=False), \
             self.assertLogs("eval", level="WARNING") as cm:
            ev.evaluate_question(CLIENT, q)
        joined = "\n".join(cm.output)
        self.assertIn("answerable question produced a not_found selection", joined)


class SecurityViolationLoggingTests(unittest.TestCase):
    def test_error_includes_source_name_but_never_chunk_text(self):
        secret_marker = "TOP_SECRET_MANAGER_ONLY_CHUNK_TEXT_MARKER_998877"
        leaking_hits = [
            _hit("ok chunk", 0.9, audience="all", source="ok.md"),
            _hit(secret_marker, 0.8, audience="manager", source="leak.md"),
        ]
        q = _q(id="SEC_Q", audience="employee")
        with patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", return_value=leaking_hits), \
             patch("eval.rerank_all", return_value=[]), \
             patch("eval.answer", return_value="the answer"), \
             patch("eval.faithfulness", return_value=(0.5, "ok")), \
             patch("eval.context_relevance", return_value=(0.5, "ok")), \
             patch("eval.completeness", return_value=(0.5, "ok")), \
             patch("eval.refused", return_value=False), \
             self.assertLogs("eval", level="ERROR") as cm:
            ev.evaluate_question(CLIENT, q)
        joined = "\n".join(cm.output)
        self.assertIn("security violation", joined)
        self.assertIn("leak.md", joined)
        self.assertNotIn(secret_marker, joined)  # the chunk TEXT must never appear


class TopLevelExceptionLoggingTests(unittest.TestCase):
    def test_exception_is_logged_with_traceback_and_still_propagates(self):
        boom = RuntimeError("simulated pipeline failure")
        with patch("eval.configure_logging"), \
             patch("eval.opensearch_client", return_value=CLIENT), \
             patch("eval.load_questions", return_value=[_q(id="BOOM_Q")]), \
             patch("eval.plan_subjects", return_value=[]), \
             patch("eval.knn_search", side_effect=boom), \
             self.assertLogs("eval", level="ERROR") as cm:
            with self.assertRaises(RuntimeError):
                ev.main()
        joined = "\n".join(cm.output)
        self.assertIn("evaluation failed", joined)
        self.assertIn("RuntimeError", joined)          # traceback text via logger.exception
        self.assertIn("simulated pipeline failure", joined)


if __name__ == "__main__":
    unittest.main()
