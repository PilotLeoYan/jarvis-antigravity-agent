#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "   Jarvis Antigravity Agent - Automated Uninstaller"
echo "=========================================================="

# Pass all arguments through to python uninstaller module
if command -v uv >/dev/null 2>&1; then
    uv run python -m jarvis_antigravity_agent.uninstaller "$@"
elif [ -f "./venv/bin/python" ]; then
    ./venv/bin/python -m jarvis_antigravity_agent.uninstaller "$@"
elif command -v python3 >/dev/null 2>&1; then
    python3 -m jarvis_antigravity_agent.uninstaller "$@"
else
    echo "[-] Error: python3 or uv is required to execute uninstaller." >&2
    exit 1
fi
