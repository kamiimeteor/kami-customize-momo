#!/bin/zsh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${DROIDRUN_PYTHON:-$HOME/droidrun-env/bin/python}"

cd "$PROJECT_DIR"
exec "$PYTHON_BIN" -m momo_cli.hotkey_voice_agent
