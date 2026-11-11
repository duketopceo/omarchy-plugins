#!/usr/bin/env bash
# Activate (select + paste) or copy-only a CopyQ history row by index.
set -euo pipefail

COPYQ="${COPYQ_BIN:-/usr/bin/copyq}"
MODE=paste
INDEX=""

while (($# > 0)); do
  case "$1" in
    --copy-only) MODE=copy; shift ;;
    --index)
      INDEX="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: copyq-activate.sh --index <n> [--copy-only]" >&2
      exit 2
      ;;
  esac
done

[[ "$INDEX" =~ ^[0-9]+$ ]] || exit 2
[[ -x $COPYQ ]] || exit 1

# Row → clipboard. CopyQ's activate_pastes then injects into the focused window
# when MODE=paste; --copy-only leaves the selection on the clipboard only.
"$COPYQ" select "$INDEX" >/dev/null
if [[ $MODE == paste ]]; then
  # Best-effort paste; some surfaces ignore it — select still updates clipboard.
  "$COPYQ" paste >/dev/null 2>&1 || true
fi
