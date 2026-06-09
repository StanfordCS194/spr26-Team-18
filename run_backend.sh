#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# ── Find Python ───────────────────────────────────────────────────────────────
# Prefer miniconda (has pydantic v2 + all deps), fall back to python3
if command -v /Users/aarzo/miniconda3/bin/python3 &>/dev/null; then
  PYTHON=/Users/aarzo/miniconda3/bin/python3
elif command -v python3 &>/dev/null; then
  PYTHON=python3
else
  echo "Error: python3 not found." >&2
  exit 1
fi

echo "Using Python: $PYTHON ($($PYTHON --version))"

# ── Check .env ────────────────────────────────────────────────────────────────
if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "Warning: .env not found. Copying from .env.example..."
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo "Fill in your API keys in .env before running."
  exit 1
fi

# ── Install deps if needed ────────────────────────────────────────────────────
if ! $PYTHON -c "import fastapi, uvicorn" &>/dev/null 2>&1; then
  echo "Installing Python dependencies..."
  $PYTHON -m pip install -r requirements.txt -q
fi

if ! $PYTHON -c "import gitpython" &>/dev/null 2>&1; then
  echo "Installing startup-risk dependencies..."
  $PYTHON -m pip install gitpython pydantic rich typer -q
fi

# ── Free port 8000 if already in use ─────────────────────────────────────────
EXISTING=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  echo "Port 8000 in use — force-stopping existing processes..."
  echo "$EXISTING" | xargs kill -9 2>/dev/null || true
  # Wait until port is actually free
  for i in 1 2 3 4 5; do
    sleep 1
    lsof -ti :8000 &>/dev/null || break
  done
fi

# ── Start ─────────────────────────────────────────────────────────────────────
echo ""
echo "Starting backend on http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo "  Press Ctrl+C to stop"
echo ""

$PYTHON -m uvicorn legi_bill.api:app --reload --port 8000
