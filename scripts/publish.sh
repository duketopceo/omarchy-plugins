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
  echo "== $id -> ${REPO[$short]}"
  git subtree push --prefix="plugins/$id" "${REPO[$short]}" main
}

if [[ ${1:-} == all ]]; then
  for k in "${!REPO[@]}"; do ship "$k"; done
elif [[ -n ${REPO[${1:-}]:-} ]]; then
  ship "$1"
else
  echo "usage: $0 <fan|ticker|agents|standby|nexus|all>" >&2
  exit 1
fi
