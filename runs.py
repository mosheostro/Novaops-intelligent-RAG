"""Saved evaluation runs, and launching new ones as an `eval.py --save`
subprocess. No Streamlit here — the UI calls these functions.

A launched run is one experiment: selected question ids from the canonical
dataset × selected configurations × an optional recency cutoff. The selection
travels as eval.py arguments; the dataset itself is never copied or changed.

A run is identified by its file stem under RUNS_DIR: `<id>.json` is the saved
EvaluationResult, `<id>.log` the subprocess output. Running processes are held
in `_procs` for the lifetime of this Python process (Streamlit keeps imported
modules across reruns); after a server restart an unfinished run with no JSON
reads as "failed".
"""
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from eval import QUESTIONS_FILE, RUNS_DIR
from models import EvaluationResult

EVAL_SCRIPT = Path(__file__).resolve().parent / "eval.py"

RunStatus = Literal["running", "done", "failed"]

_procs: dict[str, subprocess.Popen] = {}


class RunAlreadyActiveError(RuntimeError):
    """A new run was requested while another is still running."""


@dataclass(frozen=True)
class RunInfo:
    """A listed run. The experiment fields come from the saved result's
    metadata, so they are None until the run has finished and saved."""
    id: str
    status: RunStatus
    started: datetime | None
    question_ids: tuple[str, ...] | None = None
    configs: tuple[str, ...] | None = None
    cutoff: date | None = None


def _started(run_id: str) -> datetime | None:
    try:
        return datetime.strptime(run_id.partition("_")[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def run_status(run_id: str) -> RunStatus:
    proc = _procs.get(run_id)
    if proc is not None and proc.poll() is None:
        return "running"
    return "done" if (RUNS_DIR / f"{run_id}.json").is_file() else "failed"


def active_run() -> str | None:
    return next((rid for rid, p in _procs.items() if p.poll() is None), None)


def list_runs() -> list[RunInfo]:
    if not RUNS_DIR.is_dir():
        return []
    ids = {p.stem for p in RUNS_DIR.glob("*.json")} | {p.stem for p in RUNS_DIR.glob("*.log")}
    infos = []
    for rid in ids:
        status = run_status(rid)
        info = RunInfo(id=rid, status=status, started=_started(rid))
        if status == "done":
            result = load_run(rid)
            info = RunInfo(
                id=rid, status=status, started=info.started, question_ids=tuple(result.questions),
                configs=tuple(result.metadata.configs), cutoff=result.metadata.cutoff,
            )
        infos.append(info)
    return sorted(infos, key=lambda r: r.id, reverse=True)


def load_run(run_id: str) -> EvaluationResult:
    return EvaluationResult.model_validate_json((RUNS_DIR / f"{run_id}.json").read_text(encoding="utf-8"))


def launch_run(question_ids: list[str], configs: list[str], cutoff: date | None = None) -> str:
    """Start `eval.py` on the canonical dataset for exactly these question ids
    and configurations (eval.py validates both and exits on anything unknown)."""
    if not question_ids or not configs:
        raise ValueError("select at least one question and one configuration")
    if active_run() is not None:
        raise RunAlreadyActiveError("an evaluation run is already in progress")
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{QUESTIONS_FILE.stem}"
    args = ["--ids", ",".join(question_ids)]
    for name in configs:
        args += ["--config", name]
    if cutoff:
        args += ["--cutoff", cutoff.isoformat()]
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUNS_DIR / f"{run_id}.log", "w", encoding="utf-8") as log:
        _procs[run_id] = subprocess.Popen(
            [sys.executable, str(EVAL_SCRIPT), *args, "--save", "--run-id", run_id],
            stdout=log, stderr=subprocess.STDOUT, cwd=EVAL_SCRIPT.parent,
            # UTF-8: the report uses non-ASCII. Unbuffered: the UI tails this log while the run is in progress.
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        )
    return run_id


def delete_run(run_id: str) -> None:
    """Delete one saved run's artifacts (`<id>.json` and `<id>.log`). Only ids
    that list_runs() reports are accepted — the id may come from a URL, so it is
    never turned into a path otherwise. A running run cannot be deleted."""
    if run_id not in {r.id for r in list_runs()}:
        raise FileNotFoundError(f"no saved run {run_id!r}")
    if run_status(run_id) == "running":
        raise RunAlreadyActiveError(f"run {run_id!r} is still running")
    for suffix in (".json", ".log"):
        (RUNS_DIR / f"{run_id}{suffix}").unlink(missing_ok=True)
    _procs.pop(run_id, None)


def log_tail(run_id: str, lines: int = 20) -> str:
    path = RUNS_DIR / f"{run_id}.log"
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
