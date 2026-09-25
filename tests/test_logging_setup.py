"""Deterministic tests for logging_setup.py — no network, no AWS, no real
credentials.

The production `configure_logging()` API is deliberately idempotent-only: no
`force` parameter. Tests that need a clean root logger reset it themselves in
setUp/tearDown — isolation lives here, not in the production API.
"""
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import logging_setup  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _is_file_handler(h: logging.Handler) -> bool:
    return isinstance(h, RotatingFileHandler)


def _is_console_handler(h: logging.Handler) -> bool:
    return isinstance(h, logging.StreamHandler) and not _is_file_handler(h)


class _RootLoggerIsolation(unittest.TestCase):
    """Reset the root logger's handlers/level, and the third-party loggers'
    levels, around each test — so configure_logging() can be exercised from a
    clean slate without any production reconfiguration flag."""

    def setUp(self):
        root = logging.getLogger()
        self._saved_handlers = root.handlers[:]
        self._saved_level = root.level
        root.handlers = []
        self._saved_third_party = {
            name: logging.getLogger(name).level for name in logging_setup.NOISY_THIRD_PARTY_LOGGERS
        }
        for name in logging_setup.NOISY_THIRD_PARTY_LOGGERS:
            logging.getLogger(name).setLevel(logging.NOTSET)

    def tearDown(self):
        root = logging.getLogger()
        for h in root.handlers:
            h.close()
        root.handlers = self._saved_handlers
        root.setLevel(self._saved_level)
        for name, level in self._saved_third_party.items():
            logging.getLogger(name).setLevel(level)


class ConfigureLoggingTests(_RootLoggerIsolation):
    def test_creates_exactly_one_console_and_one_file_handler(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(log_file=Path(tmp) / "eval.log")
            handlers = logging.getLogger().handlers
            self.assertEqual(len(handlers), 2)
            self.assertEqual(sum(_is_console_handler(h) for h in handlers), 1)
            self.assertEqual(sum(_is_file_handler(h) for h in handlers), 1)

    def test_console_handler_defaults_to_info(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(log_file=Path(tmp) / "eval.log")
            console = next(h for h in logging.getLogger().handlers if _is_console_handler(h))
            self.assertEqual(console.level, logging.INFO)

    def test_file_handler_defaults_to_debug(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(log_file=Path(tmp) / "eval.log")
            file_handler = next(h for h in logging.getLogger().handlers if _is_file_handler(h))
            self.assertEqual(file_handler.level, logging.DEBUG)

    def test_console_handler_writes_to_stderr_not_stdout(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(log_file=Path(tmp) / "eval.log")
            console = next(h for h in logging.getLogger().handlers if _is_console_handler(h))
            self.assertIs(console.stream, sys.stderr)

    def test_custom_levels_are_respected(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(
                console_level=logging.WARNING, file_level=logging.INFO, log_file=Path(tmp) / "eval.log",
            )
            handlers = logging.getLogger().handlers
            console = next(h for h in handlers if _is_console_handler(h))
            file_handler = next(h for h in handlers if _is_file_handler(h))
            self.assertEqual(console.level, logging.WARNING)
            self.assertEqual(file_handler.level, logging.INFO)

    def test_second_call_does_not_duplicate_handlers(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            log_file = Path(tmp) / "eval.log"
            logging_setup.configure_logging(log_file=log_file)
            logging_setup.configure_logging(log_file=log_file)
            logging_setup.configure_logging(log_file=log_file)
            self.assertEqual(len(logging.getLogger().handlers), 2)

    def test_second_call_with_different_args_still_does_not_reconfigure(self):
        # Idempotent means idempotent -- the first call's settings win, silently.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(console_level=logging.INFO, log_file=Path(tmp) / "a.log")
            logging_setup.configure_logging(console_level=logging.ERROR, log_file=Path(tmp) / "b.log")
            handlers = logging.getLogger().handlers
            self.assertEqual(len(handlers), 2)
            console = next(h for h in handlers if _is_console_handler(h))
            self.assertEqual(console.level, logging.INFO)

    def test_creates_missing_log_directory(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            log_file = Path(tmp) / "nested" / "dir" / "eval.log"
            logging_setup.configure_logging(log_file=log_file)
            self.assertTrue(log_file.parent.is_dir())

    def test_a_debug_record_is_actually_written_to_the_file(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            log_file = Path(tmp) / "eval.log"
            logging_setup.configure_logging(log_file=log_file)
            logging.getLogger("some.module").debug("marker-XYZ-12345")
            for h in logging.getLogger().handlers:
                h.flush()
            self.assertIn("marker-XYZ-12345", log_file.read_text(encoding="utf-8"))

    def test_third_party_loggers_are_kept_at_warning(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(log_file=Path(tmp) / "eval.log")
            for name in logging_setup.NOISY_THIRD_PARTY_LOGGERS:
                self.assertEqual(logging.getLogger(name).level, logging.WARNING)

    def test_rotating_file_handler_uses_the_configured_rotation_settings(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            logging_setup.configure_logging(log_file=Path(tmp) / "eval.log")
            file_handler = next(h for h in logging.getLogger().handlers if _is_file_handler(h))
            self.assertEqual(file_handler.maxBytes, logging_setup.MAX_BYTES)
            self.assertEqual(file_handler.backupCount, logging_setup.BACKUP_COUNT)


class ImportSafetyTests(unittest.TestCase):
    """Importing a module must never configure global logging -- only running
    a script as __main__ does. Checked via a fresh subprocess since in-process
    state can be contaminated by earlier tests in the same run."""

    def _assert_no_handlers_after_import(self, import_statement: str) -> None:
        result = subprocess.run(
            [sys.executable, "-c",
             f"{import_statement}\nimport logging\n"
             f"assert logging.getLogger().handlers == [], logging.getLogger().handlers"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, env=dict(os.environ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_importing_logging_setup_does_not_configure_root_logger(self):
        self._assert_no_handlers_after_import("import logging_setup")

    def test_importing_eval_does_not_configure_root_logger(self):
        self._assert_no_handlers_after_import("import eval")

    def test_importing_planner_retrieval_reranker_does_not_configure_root_logger(self):
        self._assert_no_handlers_after_import("import planner, retrieval, reranker")


if __name__ == "__main__":
    unittest.main()
