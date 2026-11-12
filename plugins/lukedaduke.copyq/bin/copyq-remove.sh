#!/usr/bin/env bash
# Remove a CopyQ history row by index/tab.
set -euo pipefail

COPYQ="${COPYQ_BIN:-/usr/bin/copyq}"
INDEX=""
TAB=""
TIMEOUT_SECS=3

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
    *)
      echo "Usage: copyq-remove.sh --index <n> [--tab NAME]" >&2
      exit 2
      ;;
  esac
done

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
