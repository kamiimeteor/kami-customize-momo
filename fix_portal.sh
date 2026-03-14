#!/bin/zsh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DROIDRUN_BIN="${DROIDRUN_BIN:-$HOME/droidrun-env/bin/droidrun}"
ADB_BIN="${ADB_BIN:-/opt/homebrew/bin/adb}"
PORTAL_A11Y_SERVICE="com.droidrun.portal/.service.DroidrunAccessibilityService"

cd "$PROJECT_DIR"

echo "==> Reinstalling and re-enabling DroidRun Portal"
"$DROIDRUN_BIN" setup

echo
echo "==> Restarting Portal accessibility service"
"$ADB_BIN" shell settings put secure accessibility_enabled 0 || true
sleep 1
"$ADB_BIN" shell settings put secure enabled_accessibility_services "$PORTAL_A11Y_SERVICE" || true
"$ADB_BIN" shell settings put secure accessibility_enabled 1 || true

echo
echo "==> Waiting for Portal service to settle"
sleep 12

echo
echo "==> Checking Portal state"
"$ADB_BIN" shell content query --uri content://com.droidrun.portal/state || true
echo
"$ADB_BIN" shell content query --uri content://com.droidrun.portal/state_full || true
echo
echo "==> Checking system accessibility state"
"$ADB_BIN" shell settings get secure enabled_accessibility_services || true
"$ADB_BIN" shell settings get secure accessibility_enabled || true
echo
"$ADB_BIN" shell dumpsys accessibility | sed -n '1,40p' || true

echo
echo "If state_full still shows 'Accessibility service not available', keep the phone unlocked,"
echo "open Accessibility settings, and confirm 'Droidrun Portal' is actually shown as enabled."
