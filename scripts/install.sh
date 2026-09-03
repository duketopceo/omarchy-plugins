#!/usr/bin/env bash
# Install first-party plugins into ~/.config/omarchy/plugins.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/install.sh [--link|--copy] [--dest DIR]

  --link   Symlink plugin dirs into the Omarchy plugin folder (default).
  --copy   Copy plugin dirs (no live reload from the repo).
  --dest   Override destination (default: ~/.config/omarchy/plugins).
EOF
}

MODE=link
DEST="${HOME}/.config/omarchy/plugins"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE=link; shift ;;
    --copy) MODE=copy; shift ;;
    --dest) DEST="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

mkdir -p "$DEST"

python3 "$ROOT/scripts/validate-manifests.py"

install_one() {
  local src="$1"
  local id
  id="$(basename "$src")"
  local target="$DEST/$id"

  if [[ -L "$target" ]]; then
    local current
    current="$(readlink -f "$target" || true)"
    local desired
    desired="$(readlink -f "$src")"
    if [[ "$current" == "$desired" && "$MODE" == "link" ]]; then
      echo "unchanged $id"
      return
    fi
    rm -f "$target"
  elif [[ -d "$target" ]]; then
    local bak="${target}.bak.$(date +%s)"
    mv "$target" "$bak"
    echo "backed up $id -> $bak"
  elif [[ -e "$target" ]]; then
    echo "refusing to clobber non-directory $target" >&2
    return 1
  fi

  if [[ "$MODE" == "link" ]]; then
    ln -s "$src" "$target"
    echo "linked $id"
  else
    cp -a "$src" "$target"
    echo "copied $id"
  fi
}

shopt -s nullglob
for src in "$ROOT"/plugins/*; do
  [[ -d "$src" && -f "$src/manifest.json" ]] || continue
  install_one "$src"
done

if command -v omarchy-shell >/dev/null 2>&1; then
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
fi
