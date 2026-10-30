#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d backend ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r backend/requirements.txt
else
  echo "backend/ not present yet — skipping backend install (see MASTER_PLAN.md phase P1)"
fi

if [ -d frontend ]; then
  (cd frontend && npm ci && npm run build)
else
  echo "frontend/ not present yet — skipping frontend build (see MASTER_PLAN.md phase P2)"
fi

echo "Setup complete. Start the server with ./scripts/run.sh"
