#!/bin/bash
# TickTick MCP Server - Installation & Setup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo ""
echo "🔧  TickTick MCP Server — Installation"
echo "========================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌  Python 3 is required but not found. Please install it via: brew install python"
    exit 1
fi

echo "✅  Python $(python3 --version) found"

# Create virtual environment
echo ""
echo "📦  Creating virtual environment..."
python3 -m venv "$VENV_DIR"
echo "✅  Virtual environment created"

# Install dependencies inside venv
echo ""
echo "📦  Installing dependencies..."
"$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
echo "✅  Dependencies installed"

# Run authentication using venv Python
echo ""
echo "🔐  Starting authentication flow..."
"$VENV_DIR/bin/python3" "$SCRIPT_DIR/setup_auth.py"

# Register with Claude
echo ""
echo "📋  Registering MCP server with Claude..."
if claude mcp add ticktick -- "$VENV_DIR/bin/python3" "$SCRIPT_DIR/server.py" 2>/dev/null; then
    echo "✅  MCP server registered!"
else
    echo "⚠️   Auto-registration failed. Run this manually:"
    echo "    claude mcp add ticktick -- $VENV_DIR/bin/python3 $SCRIPT_DIR/server.py"
fi

echo ""
echo "========================================"
echo "🎉  Done! Restart Cowork and you can start adding tasks just by talking to Claude."
echo ""
