#!/usr/bin/env bash
# Install the Wisp Dashboard lock design into Lock Screen Explorer's custom
# design folder. Copies (not links): the design's relative import resolves
# against ~/.config/omarchy/lock-designs/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${LOCK_DESIGNS_DIR:-$HOME/.config/omarchy/lock-designs}"
SRC="$ROOT/lock-designs/WispDashboard.qml"

mkdir -p "$DEST"
install -m 0644 "$SRC" "$DEST/WispDashboard.qml"
echo "installed $DEST/WispDashboard.qml"

if [[ ${1:-} != --no-rescan ]] && command -v omarchy-shell >/dev/null; then
  omarchy-shell lock rescanDesigns >/dev/null 2>&1 || true
fi
