#!/bin/zsh

set -euo pipefail

PROJECT_DIR="/Users/kamiiamazing/Library/Application Support/droidrun"
DROIDRUN_BIN="${DROIDRUN_BIN:-$HOME/droidrun-env/bin/droidrun}"
ADB_BIN="${ADB_BIN:-/opt/homebrew/bin/adb}"

cd "$PROJECT_DIR"

echo "==> Reinstalling and re-enabling DroidRun Portal"
"$DROIDRUN_BIN" setup

echo
echo "==> Waiting for Portal service to settle"
sleep 12

echo
echo "==> Checking Portal state"
"$ADB_BIN" shell content query --uri content://com.droidrun.portal/state || true
echo
"$ADB_BIN" shell content query --uri content://com.droidrun.portal/state_full || true

echo
echo "If state_full still shows an error, wait another 10-20 seconds and run this script again."
