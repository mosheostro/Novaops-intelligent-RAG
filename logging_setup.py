"""Centralized logging setup — the ONLY place handlers are attached.

Operational logging is a separate concern from the Pydantic evaluation-result
contract (models.py): it never becomes part of that contract and never
duplicates the human-readable CLI report. Modules obtain a logger with
`logging.getLogger(__name__)` and configure nothing themselves; only a
script's own `main()` calls `configure_logging()`, once, as its first action.
Importing any module — including this one — never touches global logging
state, so a future API/UI process that imports e.g. `eval.evaluate()` directly
(without running `eval.py` as a script) is never surprised by a reconfigured
root logger.

    Console (stderr, WARNING+) — concise, operational; complements the CLI report.
    Rotating file (WARNING+)    — logs/eval.log; warnings and errors only;
                                   never committed (see .gitignore).

Logging levels: DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50, NOTSET=0.
NOTSET inherits the parent level; use logger.disabled = True to disable a
logger completely.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_FILE = Path("logs") / "eval.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

# boto3/botocore/urllib3/opensearch all use stdlib logging and propagate to
# root. Left alone, their own DEBUG/INFO chatter (HTTP requests, retries,
# connection details) would dominate the DEBUG file. Keep them quiet unless
# THEY have a problem worth surfacing.
NOISY_THIRD_PARTY_LOGGERS = ("boto3", "botocore", "urllib3", "opensearch")

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

def configure_logging(
    console_level: int = logging.WARNING,
    file_level: int = logging.WARNING,
    log_file: Path = DEFAULT_LOG_FILE,
) -> None:
    """Attach a stderr console handler (console_level) and a rotating file
    handler (file_level) to the root logger.

    Idempotent: a second call is a no-op (detected by a marker this function
    sets on its own handlers, not by "any handler exists" — a host process's
    own pre-existing handlers are left alone). There is deliberately no
    `force` parameter: this is the normal production entry point, called once
    per process from a script's `main()`; tests that need a clean slate reset
    the root logger themselves rather than the production API exposing a
    reconfiguration switch."""
    root = logging.getLogger()
    if any(getattr(h, "_novaops_configured", False) for h in root.handlers):
        return
    root.setLevel(logging.DEBUG)  # the handlers below do the actual filtering

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()  # defaults to sys.stderr
    console.setLevel(console_level)
    console.setFormatter(formatter)
    console._novaops_configured = True
    root.addHandler(console)

    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    file_handler._novaops_configured = True
    root.addHandler(file_handler)

    for name in NOISY_THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
