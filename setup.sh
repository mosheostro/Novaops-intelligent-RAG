#!/usr/bin/env bash
# Project bootstrap: creates .venv, installs requirements.txt, checks .env.
# Makes no AWS calls and touches no OpenSearch data. Safe to re-run.
#
#   bash setup.sh          (macOS, Linux, Windows Git Bash)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# First interpreter on PATH that runs and is Python 3.10+ (Windows may only have `python` or `py`).
PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 \
     && "$candidate" -c "import sys; sys.exit(sys.version_info < (3, 10))" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10 or newer was not found on PATH. Install it and re-run: bash setup.sh" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating virtual environment in .venv ..."
  "$PY" -m venv .venv
fi
# The venv interpreter lives in bin/ on macOS/Linux and Scripts/ on Windows.
if [ -x .venv/bin/python ]; then VENV_PY=.venv/bin/python; else VENV_PY=.venv/Scripts/python.exe; fi

echo "Installing requirements.txt ..."
"$VENV_PY" -m pip install --disable-pip-version-check -q -r requirements.txt

if [ ! -f .env ]; then
  echo "Dependencies are installed, but .env is missing." >&2
  echo "Create it from the template, fill in the values, then re-run this script:" >&2
  echo "  cp .env.example .env" >&2
  exit 1
fi

# config.py validates every required variable without any network call.
if ! problem=$("$VENV_PY" -c "import config" 2>&1); then
  echo "Configuration is incomplete:" >&2
  echo "$problem" | tail -n 1 >&2
  echo "Edit .env (see .env.example) and re-run this script." >&2
  exit 1
fi

echo "Setup complete. Activate the environment before running anything:"
echo "  source .venv/bin/activate          (Git Bash: source .venv/Scripts/activate)"
