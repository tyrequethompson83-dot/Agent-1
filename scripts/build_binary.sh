#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[build]"

PYI_ARGS=(
  --noconfirm
  --onefile
  --name agent1
  --paths src
  src/agent1/main.py
)

if [ "${CLEAN_BUILD:-0}" = "1" ]; then
  PYI_ARGS=(--clean "${PYI_ARGS[@]}")
fi

python -m PyInstaller "${PYI_ARGS[@]}"
echo "Binary build complete: ./dist/agent1"
