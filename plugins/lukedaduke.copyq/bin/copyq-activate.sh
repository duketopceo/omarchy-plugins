#!/usr/bin/env bash
# Activate (select + paste) or copy-only a CopyQ history row by index/tab.
set -euo pipefail

COPYQ="${COPYQ_BIN:-/usr/bin/copyq}"
MODE=paste
INDEX=""
TAB=""
TIMEOUT_SECS=3

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
    *)
      echo "Usage: copyq-activate.sh --index <n> [--tab NAME] [--copy-only]" >&2
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
  run_copyq tab "$TAB" select "$INDEX"
else
  run_copyq select "$INDEX"
fi

if [[ $MODE == paste ]]; then
  # Best-effort paste; some surfaces ignore it — select still updates clipboard.
  run_copyq paste 2>/dev/null || true
fi
