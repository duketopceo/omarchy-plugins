#!/usr/bin/env bash
# Activate (select + paste) or copy-only a CopyQ history row by index/tab.
# Hot vault keys use --hot-id (decrypt + copy/paste via copyq_hotkeys.py).
set -euo pipefail

COPYQ="${COPYQ_BIN:-/usr/bin/copyq}"
MODE=paste
INDEX=""
TAB=""
HOT_ID=""
TIMEOUT_SECS=3
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while (($# > 0)); do
  case "$1" in
    --copy-only) MODE=copy; shift ;;
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
      echo "Usage: copyq-activate.sh (--index <n> [--tab NAME] | --hot-id <id>) [--copy-only]" >&2
      exit 2
      ;;
  esac
done

if [[ -n $HOT_ID ]]; then
  args=(/usr/bin/python3 "$SCRIPT_DIR/copyq_hotkeys.py" activate --id "$HOT_ID")
  [[ $MODE == copy ]] && args+=(--copy-only)
  exec "${args[@]}"
fi

[[ "$INDEX" =~ ^[0-9]+$ ]] || exit 2
[[ -x $COPYQ ]] || exit 1

run_copyq() {
  /usr/bin/timeout "$TIMEOUT_SECS" "$COPYQ" "$@" >/dev/null
}

if [[ -n $TAB ]]; then
  run_copyq tab "$TAB" select "$INDEX"
else
  run_copyq select "$INDEX"
fi

if [[ $MODE == paste ]]; then
  # Give the overlay a beat to dismiss so the previous window regains focus.
  sleep 0.08
  # Best-effort paste; some surfaces ignore it — select still updates clipboard.
  run_copyq paste 2>/dev/null || true
fi
