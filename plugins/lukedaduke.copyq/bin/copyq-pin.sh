#!/usr/bin/env bash
# Copy a clipboard-tab row into the Pins tab (create tab if needed).
set -euo pipefail

COPYQ="${COPYQ_BIN:-/usr/bin/copyq}"
INDEX=""
TAB="&clipboard"
PINS_TAB="Pins"
TIMEOUT_SECS=5

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
      echo "Usage: copyq-pin.sh --index <n> [--tab NAME]" >&2
      exit 2
      ;;
  esac
done

[[ "$INDEX" =~ ^[0-9]+$ ]] || exit 2
[[ -x $COPYQ ]] || exit 1

run_copyq() {
  /usr/bin/timeout "$TIMEOUT_SECS" "$COPYQ" "$@"
}

# Already on Pins → unpin (remove that pin row).
if [[ $TAB == "$PINS_TAB" ]]; then
  run_copyq tab "$PINS_TAB" remove "$INDEX"
  exit 0
fi

formats="$(run_copyq tab "$TAB" read '?' "$INDEX" 2>/dev/null || true)"
mime=""
while IFS= read -r line; do
  case "$line" in
    image/png|image/jpeg|image/jpg|image/webp|image/bmp|image/gif)
      mime=$line
      break
      ;;
  esac
done <<< "$formats"

if [[ -n $mime ]]; then
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT
  run_copyq tab "$TAB" read "$mime" "$INDEX" >"$tmp"
  run_copyq tab "$PINS_TAB" write 0 "$mime" - <"$tmp" >/dev/null
  exit 0
fi

# Preserve trailing newlines (command substitution would strip them).
tmp_text="$(mktemp)"
trap 'rm -f "$tmp_text"' EXIT
run_copyq tab "$TAB" read "$INDEX" >"$tmp_text" 2>/dev/null || true
[[ -s $tmp_text ]] || exit 1
# Prefer insert at top of Pins.
run_copyq tab "$PINS_TAB" write 0 text/plain - <"$tmp_text" >/dev/null
