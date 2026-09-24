#!/usr/bin/env bash
# Install first-party plugins into an Omarchy plugin directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/install.sh [--link|--copy] [--dest DIR] [--backup-root DIR]
                           [--source-root DIR] [--no-rescan]

  --link         Symlink plugin dirs into the Omarchy plugin folder (default).
  --copy         Copy plugin dirs without development symlinks (release path).
  --dest         Override destination (default: ~/.config/omarchy/plugins).
  --backup-root  Store displaced/legacy backups outside the discovery root.
  --source-root  Use another source checkout (primarily for tests).
  --no-rescan    Do not ask the host shell to rescan plugins.
EOF
}

MODE=link
DEST="${HOME}/.config/omarchy/plugins"
BACKUP_ROOT="${OMARCHY_PLUGIN_BACKUP_ROOT:-${XDG_STATE_HOME:-${HOME}/.local/state}/omarchy-plugins/backups}"
SOURCE_ROOT="$ROOT"
RESCAN=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE=link; shift ;;
    --copy) MODE=copy; shift ;;
    --dest)
      [[ $# -ge 2 ]] || { echo "--dest requires a directory" >&2; exit 2; }
      DEST="$2"; shift 2 ;;
    --backup-root)
      [[ $# -ge 2 ]] || { echo "--backup-root requires a directory" >&2; exit 2; }
      BACKUP_ROOT="$2"; shift 2 ;;
    --source-root)
      [[ $# -ge 2 ]] || { echo "--source-root requires a directory" >&2; exit 2; }
      SOURCE_ROOT="$2"; shift 2 ;;
    --no-rescan) RESCAN=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

SOURCE_PLUGINS="$SOURCE_ROOT/plugins"
VALIDATE="$ROOT/scripts/validate-manifests.py"
[[ -d "$SOURCE_PLUGINS" ]] || { echo "source plugin directory is unavailable" >&2; exit 1; }
case "$BACKUP_ROOT/" in
  "$DEST/"*)
    echo "backup root must be outside the plugin discovery root" >&2
    exit 1
    ;;
esac

mkdir -p "$DEST"
python3 "$VALIDATE"
python3 "$VALIDATE" --install-root "$DEST" --allow-symlink --ignore-legacy-backups

migrate_legacy_backups() {
  shopt -s nullglob
  local legacy backup_name backup_target
  for legacy in "$DEST"/*.bak.*; do
    [[ -d "$legacy" && -f "$legacy/manifest.json" ]] || continue
    mkdir -p "$BACKUP_ROOT"
    backup_name="$(basename "$legacy")"
    backup_target="$BACKUP_ROOT/$backup_name"
    if [[ -e "$backup_target" ]]; then
      backup_target="$BACKUP_ROOT/$backup_name.$(date +%s%N)"
    fi
    mv "$legacy" "$backup_target"
    echo "migrated legacy backup $backup_name -> $backup_target"
  done
}

migrate_legacy_backups
python3 "$VALIDATE" --install-root "$DEST" --allow-symlink

move_to_backup() {
  local target="$1" id backup_target
  id="$(basename "$target")"
  mkdir -p "$BACKUP_ROOT"
  backup_target="$BACKUP_ROOT/$id.$(date +%s%N)"
  while [[ -e "$backup_target" ]]; do
    backup_target="$BACKUP_ROOT/$id.$(date +%s%N)-$RANDOM"
  done
  mv "$target" "$backup_target"
  echo "backed up $id -> $backup_target"
}

copy_plugin() {
  local src="$1" id="$2" target="$3" staging
  staging="$BACKUP_ROOT/.release-$id-$$"
  rm -rf "$staging"
  mkdir -p "$staging"
  tar \
    --exclude='*/__pycache__' \
    --exclude='*.pyc' \
    --exclude='*/node_modules' \
    --exclude='*/target' \
    --exclude='*/build' \
    --exclude='*/dist' \
    -C "$SOURCE_PLUGINS" -cf - "$id" | tar -C "$staging" -xf -
  mv "$staging/$id" "$target"
  rmdir "$staging"
}

install_one() {
  local src="$1"
  local id target
  id="$(basename "$src")"
  target="$DEST/$id"

  if [[ -L "$target" ]]; then
    local current desired
    current="$(readlink -f "$target" || true)"
    desired="$(readlink -f "$src")"
    if [[ "$current" == "$desired" && "$MODE" == "link" ]]; then
      echo "unchanged $id"
      return
    fi
    rm -f "$target"
  elif [[ -d "$target" ]]; then
    move_to_backup "$target"
  elif [[ -e "$target" ]]; then
    echo "refusing to clobber non-directory $target" >&2
    return 1
  fi

  if [[ "$MODE" == "link" ]]; then
    ln -s "$src" "$target"
    echo "linked $id"
  else
    copy_plugin "$src" "$id" "$target"
    echo "copied $id"
  fi
}

shopt -s nullglob
for src in "$SOURCE_PLUGINS"/*; do
  [[ -d "$src" && -f "$src/manifest.json" ]] || continue
  install_one "$src"
done

if [[ "$MODE" == "copy" ]]; then
  python3 "$VALIDATE" --install-root "$DEST" --release
fi

if [[ "$RESCAN" == "1" ]] && command -v omarchy-shell >/dev/null 2>&1; then
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
fi
