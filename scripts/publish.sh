#!/usr/bin/env bash
# Push a plugin subdir to its own public repo via git subtree.
# Usage: scripts/publish.sh <id|all>   e.g. scripts/publish.sh fan
set -euo pipefail

cd "$(dirname "$0")/.."

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
)

ship() {
  local id="$1" short="${1##*.}"
  [[ -d "plugins/$id" ]] || { echo "no such plugin: $id"; return 1; }
  local remote="${REPO[$id]}"
  echo "== $id -> $remote"

  local split
  split=$(git subtree split --prefix="plugins/$id" HEAD 2>/dev/null | tail -n1)
  [[ -n "$split" ]] || { echo "  split failed"; return 1; }

  # Fast path: remote tip is inside our split history -> plain FF push.
  if git push "$remote" "$split:refs/heads/main" 2>/dev/null; then
    return
  fi

  # Remote has commits our split doesn't contain (fixes pushed repo-side,
  # e.g. marketplace security review at a pinned SHA). Reconcile by
  # committing our subtree content on top of the remote tip — always a
  # fast-forward, remote history preserved. Adopt that commit back with a
  # -Xsubtree merge afterwards (see docs/UPSTREAM.md).
  echo "  remote diverged; reconciling on top of remote main"
  git fetch "$remote" "+main:refs/child/$short"
  local merged
  merged=$(git commit-tree "$split^{tree}" -p "refs/child/$short" \
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

if [[ ${1:-} == all ]]; then
  for k in "${!REPO[@]}"; do ship "$k"; done
elif id=$(resolve "${1:-}"); then
  ship "$id"
else
  echo "usage: $0 <plugin-id-or-short-name|all>" >&2
  printf 'known: %s\n' "${!REPO[@]}" >&2
  exit 1
fi
