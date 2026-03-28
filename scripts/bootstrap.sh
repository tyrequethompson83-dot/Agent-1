#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

if [ "${SKIP_PLAYWRIGHT:-0}" != "1" ]; then
  python -m playwright install chromium
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

if [ "${RUN_INIT:-0}" = "1" ]; then
  python -m agent1.main init --style "${INIT_STYLE:-home}"
fi

if [ "${RUN_ONBOARD:-0}" = "1" ]; then
  python -m agent1.main onboard --style "${INIT_STYLE:-home}" --doctor-fix
fi

echo "Bootstrap complete."
