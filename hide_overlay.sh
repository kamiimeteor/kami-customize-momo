#!/bin/zsh

set -euo pipefail

PROJECT_DIR="/Users/kamiiamazing/Library/Application Support/droidrun"
PYTHON_BIN="${DROIDRUN_PYTHON:-$HOME/droidrun-env/bin/python}"

cd "$PROJECT_DIR"
exec "$PYTHON_BIN" hide_overlay.py
