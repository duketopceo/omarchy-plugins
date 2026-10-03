#!/usr/bin/env bash
# Push a plugin subdir to its own public repo via git subtree.
# Usage: scripts/publish.sh [--allow-delete] <id|all>   e.g. scripts/publish.sh fan
#
# Before any push, a dry-run diff compares the split tree with the remote's
# main: if the remote has files the split lacks (the push would delete them),
# publishing refuses unless --allow-delete is given. Never force-pushes.
set -euo pipefail

UMBRELLA="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_CHECK="$UMBRELLA/scripts/check-release-readiness.py"
SYNC_SHARED="$UMBRELLA/scripts/sync-shared.py"
ALLOW_DELETE=""

# Keyed by full plugin id — the directory name under plugins/.
declare -A REPO=(
  [lukedaduke.fan]="git@github.com:duketopceo/omarchy-fan.git"
  [lukedaduke.ticker]="git@github.com:duketopceo/omarchy-ticker.git"
  [lukedaduke.agents]="git@github.com:duketopceo/omarchy-agents.git"
  [lukedaduke.standby]="git@github.com:duketopceo/omarchy-standby.git"
  [lukedaduke.nexus]="git@github.com:duketopceo/omarchy-nexus.git"
  [lukedaduke.connections]="git@github.com:duketopceo/omarchy-connections.git"
  [lukedaduke.power]="git@github.com:duketopceo/omarchy-power.git"
  [io.github.duketopceo.bumblebee]="git@github.com:duketopceo/omarchy-bumblebee.git"
  [io.github.duketopceo.numbat]="git@github.com:duketopceo/omarchy-numbat.git"
  [io.github.duketopceo.pplx]="git@github.com:duketopceo/omarchy-pplx.git"
  [io.github.duketopceo.neo]="git@github.com:duketopceo/omarchy-neo.git"
)

# Dry-run diff: list files present on the remote ref but absent from the
# split (what publishing would delete). Refuse unless --allow-delete.
# Usage: guard_deletions <split> <remote-ref|""> [--allow-delete]
guard_deletions() {
  local split="$1" remote_ref="$2" allow="${3:-}" gone count
  [[ -n $remote_ref ]] || return 0
  gone=$(git diff --name-only --no-renames --diff-filter=D "$remote_ref" "$split") || {
    echo "  dry-run diff against $remote_ref failed" >&2
    return 1
  }
  [[ -n $gone ]] || return 0
  count=$(printf '%s\n' "$gone" | wc -l)
  echo "  dry-run: publishing would delete $count remote-only file(s):"
  printf '%s\n' "$gone" | sed 's/^/    - /'
  if [[ $allow == --allow-delete ]]; then
    echo "  --allow-delete given; proceeding"
    return 0
  fi
  echo "  refusing: the remote has files the umbrella lacks; adopt them into" >&2
  echo "  plugins/<id>/ first (see docs/UPSTREAM.md) or re-run with --allow-delete" >&2
  return 1
}

is_shared_consumer() {
  [[ -f "$UMBRELLA/shared/consumers.txt" ]] || return 1
  sed 's/#.*//; s/[[:space:]]//g' "$UMBRELLA/shared/consumers.txt" | grep -qxF "$1"
}

# Re-check every vendored shared library inside the split output itself:
# Python in bin/_omplug and, when shared/qml exists, QML in lib/.
check_split_shared() {
  local split="$1" tmp rc=0 pair dest src
  local pairs=("bin/_omplug:shared/py/_omplug")
  [[ -d "$UMBRELLA/shared/qml" ]] && pairs+=("lib:shared/qml")
  for pair in "${pairs[@]}"; do
    dest="${pair%%:*}" src="${pair#*:}"
    tmp=$(mktemp -d)
    if git archive "$split" "$dest" 2>/dev/null | tar -x -C "$tmp"; then
      python3 "$SYNC_SHARED" --check-dir "$tmp/$dest" --src "$src" || rc=1
    else
      echo "  split has no $dest but plugin is a shared consumer" >&2
      rc=1
    fi
    rm -rf "$tmp"
  done
  return "$rc"
}

ship() {
  local id="$1" short="${1##*.}"
  [[ -d "plugins/$id" ]] || { echo "no such plugin: $id"; return 1; }
  local remote="${REPO[$id]}"
  echo "== $id -> $remote"
  python3 "$RELEASE_CHECK" --plugin-id "$id" --format text

  local split
  split=$(git subtree split --prefix="plugins/$id" HEAD 2>/dev/null | tail -n1)
  [[ -n "$split" ]] || { echo "  split failed"; return 1; }

  if is_shared_consumer "$id"; then
    check_split_shared "$split" || { echo "  split shared library drift"; return 1; }
  fi

  # Fetch the remote tip (if the repo has a main yet) for the dry-run diff.
  local remote_ref="" rc=0
  git ls-remote --exit-code "$remote" refs/heads/main >/dev/null || rc=$?
  if [[ $rc == 0 ]]; then
    git fetch -q "$remote" "+main:refs/child/$short"
    remote_ref="refs/child/$short"
  elif [[ $rc != 2 ]]; then
    echo "  cannot reach $remote"; return 1
  fi
  guard_deletions "$split" "$remote_ref" "$ALLOW_DELETE" || return 1

  # Fast path: remote tip is inside our split history -> plain FF push.
  if [[ -z $remote_ref ]] || git merge-base --is-ancestor "$remote_ref" "$split"; then
    git push "$remote" "$split:refs/heads/main"
    return
  fi

  # Remote has commits our split doesn't contain (fixes pushed repo-side,
  # e.g. marketplace security review at a pinned SHA). Reconcile by
  # committing our subtree content on top of the remote tip — always a
  # fast-forward, remote history preserved. Adopt that commit back with a
  # -Xsubtree merge afterwards (see docs/UPSTREAM.md).
  echo "  remote diverged; reconciling on top of remote main"
  local merged
  merged=$(git commit-tree "$split^{tree}" -p "$remote_ref" \
    -m "sync: update from omarchy-plugins umbrella")
  git push "$remote" "$merged:refs/heads/main"
}

# Accept a full plugin id or its unique last segment (fan -> lukedaduke.fan,
# pplx -> io.github.duketopceo.pplx).
resolve() {
  local arg="$1" id
  [[ -n $arg && -n ${REPO[$arg]:-} ]] && { echo "$arg"; return; }
  for id in "${!REPO[@]}"; do
    [[ ${id##*.} == "$arg" ]] && { echo "$id"; return; }
  done
  return 1
}

main() {
  cd "$UMBRELLA"
  local args=() arg id
  for arg in "$@"; do
    case "$arg" in
      --allow-delete) ALLOW_DELETE="--allow-delete" ;;
      *) args+=("$arg") ;;
    esac
  done
  if [[ ${args[0]:-} == all ]]; then
    for id in "${!REPO[@]}"; do ship "$id"; done
  elif id=$(resolve "${args[0]:-}"); then
    ship "$id"
  else
    echo "usage: $0 [--allow-delete] <plugin-id-or-short-name|all>" >&2
    printf 'known: %s\n' "${!REPO[@]}" >&2
    exit 1
  fi
}

# Sourcing (tests) defines the functions without publishing anything.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
