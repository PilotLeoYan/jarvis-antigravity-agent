#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   Jarvis Antigravity Agent - Automated Environment Setup"
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Dependency Checks
echo "[+] Checking system prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo >&2 "[-] Error: python3 is required. Aborting."; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo >&2 "[-] Warning: ffmpeg is not installed. Voice note processing requires ffmpeg (sudo apt install ffmpeg)."; }
command -v agy >/dev/null 2>&1 || { echo >&2 "[*] Note: Google Antigravity CLI ('agy') not found in PATH. Ensure it is installed in ~/.local/bin or specify its absolute path in config.yaml."; }

# 2. Install package with uv (preferred) or fallback to pip venv
if command -v uv >/dev/null 2>&1; then
    echo "[+] Installing package with uv..."
    uv sync
    echo "[+] Package installed. Entrypoints available: jarvis-antigravity-agent, jarvis-send-message, jarvis-spawn-agent, jarvis-mcp, jarvis-update, jarvis-uninstall"
else
    echo "[+] uv not found — falling back to pip venv..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -e .
fi

# 3. Configuration Scaffolding
if [ ! -f "config.yaml" ] && [ ! -f "config.yml" ] && [ ! -f "config.json" ]; then
    echo "[+] Creating config.yaml from template..."
    cp config.example.yaml config.yaml
    echo "[*] Remember to edit config.yaml with your Telegram Bot Token and User ID."
else
    echo "[+] Configuration file already exists."
fi

# 4. Cognitive Setup
AGENT_CONFIG_DIR="$HOME/.gemini/config"
mkdir -p "$AGENT_CONFIG_DIR"
if [ ! -f "$AGENT_CONFIG_DIR/SOUL.md" ]; then
    echo "[+] Deploying cognitive rules to $AGENT_CONFIG_DIR/SOUL.md..."
    cp cognitive/SOUL.md "$AGENT_CONFIG_DIR/SOUL.md"
fi

# 5. Skills Deployment (Standard AGY User Skills Locations)
SKILL_TARGET_DIRS=(
    "$HOME/.gemini/config/skills"
    "$HOME/.agents/skills"
)
echo "[+] Copying custom skills into standard AGY user skills locations..."
for target_dir in "${SKILL_TARGET_DIRS[@]}"; do
    mkdir -p "$target_dir"
    for skill in "$SCRIPT_DIR/skills"/*; do
        if [ -d "$skill" ] && [ -f "$skill/SKILL.md" ]; then
            sname=$(basename "$skill")
            dest="$target_dir/$sname"
            rm -rf "$dest"
            cp -r "$skill" "$dest"
            echo "    Copied skill: $sname -> $dest"
        fi
    done
done

# 6. Binary Symlinks Linking to ~/.local/bin
USER_BIN_DIR="$HOME/.local/bin"
mkdir -p "$USER_BIN_DIR"
VENV_BIN_DIR="$SCRIPT_DIR/.venv/bin"
if [ ! -d "$VENV_BIN_DIR" ]; then
    VENV_BIN_DIR="$SCRIPT_DIR/venv/bin"
fi

if [ ! -d "$VENV_BIN_DIR" ]; then
    echo >&2 "[-] Error: Virtual environment binary directory not found at $VENV_BIN_DIR."
    echo >&2 "    Please verify that package installation in Step 2 succeeded."
    exit 1
fi

ENTRYPOINTS=(
    "jarvis-antigravity-agent"
    "jarvis-send-message"
    "jarvis-spawn-agent"
    "jarvis-mcp"
    "jarvis-update"
    "jarvis-uninstall"
)

echo "[+] Linking executable entrypoints into $USER_BIN_DIR..."
for ep in "${ENTRYPOINTS[@]}"; do
    if [ -f "$VENV_BIN_DIR/$ep" ]; then
        ln -sf "$VENV_BIN_DIR/$ep" "$USER_BIN_DIR/$ep"
        chmod +x "$USER_BIN_DIR/$ep" 2>/dev/null || true
        echo "    Linked binary: $ep -> $USER_BIN_DIR/$ep"
    else
        echo >&2 "    [-] Warning: Entrypoint $ep not found in $VENV_BIN_DIR"
    fi
done

# Ensure core daemon executable is verified before systemd setup
if [ ! -x "$USER_BIN_DIR/jarvis-antigravity-agent" ]; then
    echo >&2 "[-] Fatal Error: $USER_BIN_DIR/jarvis-antigravity-agent is missing or not executable."
    echo >&2 "    Cannot proceed with systemd service installation (would cause status 203/EXEC)."
    exit 1
fi

# 7. Systemd Service Deployment
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"
if [ -f "$SCRIPT_DIR/systemd/agy-telegram.service" ]; then
    echo "[+] Deploying systemd user service template to $SYSTEMD_USER_DIR/agy-telegram.service..."
    cp "$SCRIPT_DIR/systemd/agy-telegram.service" "$SYSTEMD_USER_DIR/agy-telegram.service"
    chmod 644 "$SYSTEMD_USER_DIR/agy-telegram.service" 2>/dev/null || true
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload 2>/dev/null || true
    fi
fi

echo ""
echo "=========================================================="
echo "   Setup Complete!"
if [[ ":$PATH:" != *":$USER_BIN_DIR:"* ]]; then
    echo ""
    echo "   [*] Note: $USER_BIN_DIR is not currently in your PATH."
    echo "       To run commands directly, add it to your shell profile:"
    echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo ""
echo "   To start manually:"
echo "     jarvis-antigravity-agent"
echo ""
echo "   To enable and start as a systemd user daemon:"
echo "     systemctl --user enable --now agy-telegram.service"
echo ""
echo "   To reload and start the service on your system:"
echo "     systemctl --user daemon-reload"
echo "     systemctl --user restart agy-telegram.service"
echo "     systemctl --user status agy-telegram.service"
echo ""
echo "   To view service logs:"
echo "     journalctl --user -u agy-telegram.service -f"
echo "================================================================"
