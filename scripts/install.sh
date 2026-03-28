#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STYLE="${STYLE:-home}"
SKIP_PLAYWRIGHT="${SKIP_PLAYWRIGHT:-0}"
SKIP_ONBOARD="${SKIP_ONBOARD:-0}"
START_SERVICES="${START_SERVICES:-0}"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

if [ "$SKIP_PLAYWRIGHT" != "1" ]; then
  python -m playwright install chromium
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

if [ "$SKIP_ONBOARD" != "1" ]; then
  args=( -m agent1.main onboard --style "$STYLE" --doctor-fix )
  if [ "$START_SERVICES" = "1" ]; then
    args+=( --up )
  fi
  python "${args[@]}"
fi

echo "Install complete."
echo "Next: ./.venv/bin/python -m agent1.main"
