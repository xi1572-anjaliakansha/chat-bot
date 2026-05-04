#!/usr/bin/env bash
# Always uses backend/venv so packages from requirements.txt (e.g. langchain-openai) are available.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ ! -x venv/bin/python ]]; then
  echo "Creating venv in $ROOT/venv ..."
  python3 -m venv venv
fi
# shellcheck source=/dev/null
source venv/bin/activate
pip install -q -r requirements.txt
exec python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
