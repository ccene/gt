#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d backend ]; then
  echo "backend/ not present yet — nothing to run (see MASTER_PLAN.md phase P1)"
  exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ -d .venv ]; then
  PY=.venv/bin/python
else
  PY=python3
fi

echo "Serving on http://${HOST}:${PORT} — open the LAN IP on each player's device"
cd backend
exec "$PY" -m uvicorn main:app --host "$HOST" --port "$PORT"
