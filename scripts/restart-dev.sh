#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_LOG="/tmp/openbidkit-backend.log"
FRONTEND_LOG="/tmp/openbidkit-frontend.log"

cd "$ROOT_DIR"

pkill -f "react-scripts start" 2>/dev/null || true
pkill -f "$ROOT_DIR/frontend/node_modules/.bin/react-scripts" 2>/dev/null || true
fuser -k 3000/tcp 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true

sleep 1

: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

setsid env DEBUG=false "$ROOT_DIR/.venv/bin/python" backend/run.py \
  > "$BACKEND_LOG" 2>&1 < /dev/null &

# react-scripts can stop when its stdin closes. Keep stdin open with tail.
setsid bash -lc "cd '$ROOT_DIR/frontend' && tail -f /dev/null | env HOST=0.0.0.0 BROWSER=none npm start" \
  > "$FRONTEND_LOG" 2>&1 < /dev/null &

sleep 6

echo "Listening ports:"
ss -ltnp | grep -E ':3000|:8000' || true

echo
echo "Backend log:"
tail -20 "$BACKEND_LOG"

echo
echo "Frontend log:"
tail -30 "$FRONTEND_LOG"
