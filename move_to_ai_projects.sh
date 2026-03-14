#!/bin/zsh

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_PARENT="$HOME/Documents/AI_projects"
TARGET_DIR="$TARGET_PARENT/momo-droidrun"

if [[ ! -d "$TARGET_PARENT" ]]; then
  echo "Target parent directory does not exist: $TARGET_PARENT" >&2
  exit 1
fi

if [[ -e "$TARGET_DIR" ]]; then
  echo "Target already exists: $TARGET_DIR" >&2
  exit 1
fi

echo "Moving project:"
echo "  from: $SOURCE_DIR"
echo "  to:   $TARGET_DIR"

mv "$SOURCE_DIR" "$TARGET_DIR"

echo
echo "Move complete."
echo "New project path:"
echo "  $TARGET_DIR"
