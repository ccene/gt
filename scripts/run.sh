#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d backend ]; then
  echo "backend/ not present yet — nothing to run (see MASTER_PLAN.md phase P1)"
  exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

# Absolute path so the venv resolves no matter the cwd after `cd backend`.
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY=python3
fi

echo "Serving on http://${HOST}:${PORT} — open the LAN IP on each player's device"
cd backend
exec "$PY" -m uvicorn main:app --host "$HOST" --port "$PORT"
