#!/bin/bash
# Agent Mall — One-click launch
# Usage: bash start.sh

set -e

PORT="${PORT:-7030}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🏬 Agent 互联网一号商场"
echo "========================="

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Install Python 3.10+ first."
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYVER"

# Install deps
echo "📦 Installing dependencies..."
pip3 install -q fastapi uvicorn httpx openai 2>/dev/null
echo "✅ Dependencies OK"

# Load .env if exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "🔑 Loading .env..."
    set -a; source "$SCRIPT_DIR/.env"; set +a
fi

# Show status
if [ -n "$DEEPSEEK_API_KEY" ]; then
    DKEY="${DEEPSEEK_API_KEY:0:8}...${DEEPSEEK_API_KEY: -4}"
    echo "🧠 DeepSeek V4: $DKEY"
else
    echo "⚠️  No DEEPSEEK_API_KEY — Agents will use fallback replies"
    echo "   Get one: https://platform.deepseek.com/api_keys"
    echo "   Then: export DEEPSEEK_API_KEY=sk-..."
fi

echo ""
echo "🚀 Starting AMP on http://0.0.0.0:$PORT"
echo "   Open http://localhost:$PORT in your browser"
echo "   Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR"
exec python3 main.py
