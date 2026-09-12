#!/usr/bin/env bash
# Push a plugin subdir to its own public repo via git subtree.
# Usage: scripts/publish.sh <id|all>   e.g. scripts/publish.sh fan
set -euo pipefail

cd "$(dirname "$0")/.."

declare -A REPO=(
  [fan]="git@github.com:duketopceo/omarchy-fan.git"
  [ticker]="git@github.com:duketopceo/omarchy-ticker.git"
  [agents]="git@github.com:duketopceo/omarchy-agents.git"
  [standby]="git@github.com:duketopceo/omarchy-standby.git"
  [nexus]="git@github.com:duketopceo/omarchy-nexus.git"
)

ship() {
  local short="$1" id="lukedaduke.$1"
  [[ -d "plugins/$id" ]] || { echo "no such plugin: $id"; return 1; }
  local remote="${REPO[$short]}"
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

if [[ ${1:-} == all ]]; then
  for k in "${!REPO[@]}"; do ship "$k"; done
elif [[ -n ${REPO[${1:-}]:-} ]]; then
  ship "$1"
else
  echo "usage: $0 <fan|ticker|agents|standby|nexus|all>" >&2
  exit 1
fi
