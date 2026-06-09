#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$REPO_ROOT/frontend"

cd "$FRONTEND"

# ── Check node ────────────────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
  echo "Error: node not found. Install Node.js from https://nodejs.org" >&2
  exit 1
fi

echo "Using Node: $(node --version)  npm: $(npm --version)"

# ── Install deps if needed ────────────────────────────────────────────────────
if [ ! -d node_modules ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

# ── Free port 5173 if already in use ─────────────────────────────────────────
EXISTING=$(lsof -ti :5173 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  echo "Port 5173 in use — stopping existing processes..."
  echo "$EXISTING" | xargs kill 2>/dev/null || true
  sleep 1
fi

# ── Start ─────────────────────────────────────────────────────────────────────
echo ""
echo "Starting frontend on http://localhost:5173"
echo "  Backend proxy: /api → http://localhost:8000"
echo "  Press Ctrl+C to stop"
echo ""

npm run dev
