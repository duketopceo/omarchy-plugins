#!/usr/bin/env bash
# Remove a CopyQ history row by index/tab, or drop a hot-vault key by --hot-id.
set -euo pipefail

COPYQ="${COPYQ_BIN:-/usr/bin/copyq}"
INDEX=""
TAB=""
HOT_ID=""
TIMEOUT_SECS=3
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while (($# > 0)); do
  case "$1" in
    --index)
      INDEX="${2:-}"
      shift 2
      ;;
    --tab)
      TAB="${2:-}"
      shift 2
      ;;
    --hot-id)
      HOT_ID="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: copyq-remove.sh (--index <n> [--tab NAME] | --hot-id <id>)" >&2
      exit 2
      ;;
  esac
done

if [[ -n $HOT_ID ]]; then
  exec /usr/bin/python3 "$SCRIPT_DIR/copyq_hotkeys.py" drop --id "$HOT_ID"
fi

[[ "$INDEX" =~ ^[0-9]+$ ]] || exit 2
[[ -x $COPYQ ]] || exit 1

run_copyq() {
  /usr/bin/timeout "$TIMEOUT_SECS" "$COPYQ" "$@" >/dev/null
}

if [[ -n $TAB ]]; then
  run_copyq tab "$TAB" remove "$INDEX"
else
  run_copyq remove "$INDEX"
fi
