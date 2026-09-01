#!/bin/bash
# Shop.ai — one-shot startup script
# Run this from the project root: bash scripts/start.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "Shop.ai Startup"
echo "=================================="

# ── 1. Python venv ────────────────────────────────────────────────
if [ ! -d "venv" ]; then
  echo "→ Creating Python virtualenv..."
  python3 -m venv venv
fi

echo "→ Activating venv and installing Python deps..."
source venv/bin/activate
pip install -r requirements.txt -q

# ── 2. Database ───────────────────────────────────────────────────
# SQLite tables are created by the application on startup.

# ── 3. Frontend deps ──────────────────────────────────────────────
echo "→ Installing frontend dependencies..."
cd frontend
npm install
cd "$PROJECT_DIR"

# ── 4. Check .env ─────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Created .env from .env.example"
  echo "   Add your keys before the agents can call Gemini or Razorpay:"
  echo "   GEMINI_API_KEY=..."
  echo "   RAZORPAY_KEY_ID=..."
  echo "   RAZORPAY_KEY_SECRET=..."
  echo ""
fi

# ── 5. Start both servers ─────────────────────────────────────────
echo ""
echo "✅ Starting servers..."
echo "   Backend  → http://localhost:8000"
echo "   Frontend → http://localhost:5173"
echo ""

# Backend in background
source venv/bin/activate
uvicorn app.api.main:app --port 8000 --reload &
BACKEND_PID=$!

# Frontend in background
cd frontend && npm run dev &
FRONTEND_PID=$!

cd "$PROJECT_DIR"

echo "Servers running. Press Ctrl+C to stop both."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT TERM

wait
