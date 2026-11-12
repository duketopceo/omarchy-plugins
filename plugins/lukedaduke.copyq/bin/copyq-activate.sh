#!/usr/bin/env bash
# Activate (select + paste) or copy-only a CopyQ history row by index/tab.
set -euo pipefail

COPYQ="${COPYQ_BIN:-/usr/bin/copyq}"
WTYPE="${WTYPE_BIN:-/usr/bin/wtype}"
HYPRCTL="${HYPRCTL_BIN:-/usr/bin/hyprctl}"
JQ="${JQ_BIN:-/usr/bin/jq}"
MODE=paste
INDEX=""
TAB=""
TIMEOUT_SECS=3
PASTE_DELAY="${COPYQ_PASTE_DELAY:-0.2}"

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

# copyq paste cannot inject keys on Wayland, so mirror Omarchy's universal
# paste instead: Ctrl+Shift+V into terminals, Ctrl+V elsewhere, via wtype's
# virtual-keyboard protocol. The delay lets focus return to the window the
# overlay covered before the chord lands.
paste_chord() {
  if [[ ! -x $WTYPE ]]; then
    run_copyq paste 2>/dev/null || true
    return
  fi
  local is_terminal=0 tags="" tag
  if [[ -x $HYPRCTL && -x $JQ ]]; then
    tags="$("$HYPRCTL" activewindow -j 2>/dev/null | "$JQ" -r '(.tags // [])[]' 2>/dev/null || true)"
  fi
  while IFS= read -r tag; do
    tag="${tag%\*}"
    if [[ $tag == "terminal" ]]; then
      is_terminal=1
      break
    fi
  done <<< "$tags"
  if (( is_terminal )); then
    "$WTYPE" -M ctrl -M shift -k v -m shift -m ctrl 2>/dev/null || true
  else
    "$WTYPE" -M ctrl -k v -m ctrl 2>/dev/null || true
  fi
}

if [[ -n $TAB ]]; then
  run_copyq tab "$TAB" select "$INDEX"
else
  run_copyq select "$INDEX"
fi

if [[ $MODE == paste ]]; then
  sleep "$PASTE_DELAY"
  paste_chord
fi
