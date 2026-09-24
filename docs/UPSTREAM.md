# Upstream path

This repo is **public**. It is the authoring tree and the laptop index for the
`lukedaduke.*` plugins — the source of truth for everything under `plugins/`.

The umbrella itself is not submitted to the marketplace. Marketplace listings
require a **public** GitHub repo with `manifest.json` at the repository root
([publish guide](https://plugins.omarchy.org/publish.html)). `omarchy plugin
add` has the same constraint, so each plugin ships from its own repo.

## Installation and discovery integrity

`omarchy plugin add` and the host registry discover plugin directories by
manifest. Keep the live discovery root limited to the intended plugin IDs:

- Development installs use `scripts/install.sh --link`.
- Release installs use `scripts/install.sh --copy`; generated Python/Node
  artifacts and symlinks are excluded from the copy and rejected by validation.
- Legacy `*.bak.*` directories are moved to
  `${XDG_STATE_HOME:-$HOME/.local/state}/omarchy-plugins/backups` (or the
  explicit `--backup-root`) before a rescan. They remain available for rollback
  but are no longer candidates for discovery.
- Duplicate non-backup manifest IDs fail preflight before installation changes
  the intended source tree.

The repository `catalog.json` is authoring metadata, not the host registry. Use
the supported host rescan after a reversible install migration; do not hand-edit
host-owned registry state.

## Sync model

- **Outbound (publish):** `scripts/publish.sh <id|all>` subtree-pushes
  `plugins/lukedaduke.<id>/` to `duketopceo/omarchy-<id>` `main`. Run it after
  any plugin change that should ship. If the standalone repo has diverged
  (fixes pushed repo-side, e.g. marketplace review), the script reconciles by
  committing our subtree content on top of the remote tip — always a
  fast-forward, never a force-push.
- **Inbound (adopt):** fixes sometimes land on a standalone repo directly
  (e.g. marketplace security review at a pinned SHA). Bring them home with a
  subtree merge so the umbrella stays authoritative and the next `publish.sh`
  is a fast-forward:

  ```sh
  git fetch git@github.com:duketopceo/omarchy-<id>.git +main:refs/child/<id>
  git merge --allow-unrelated-histories \
    -Xsubtree=plugins/lukedaduke.<id> refs/child/<id>
  # resolve plugin-dir conflicts with --theirs (standalone is published truth)
  ```

  Plain `git subtree pull` refuses here because the standalone histories are
  synthetic splits — unrelated to the umbrella DAG until first merged.

## Official marketplace (community plugins)

To list a new plugin:

1. `scripts/publish.sh <id>` so the standalone public repo is current.
2. Run `omarchy plugin validate` on a checkout of the standalone repo.
3. Open a submission issue on `omacom/omarchy-plugin-marketplace` — see
   `.devin/skills/omarchy-marketplace-submission/` for the exact body format.
   Editing the issue re-runs validation; comments do not.

## What stays out of the standalone repos

- `machine/` restore index
- Host-specific helpers that assume Dell fan control / local PATH
- Anything that is not a self-contained plugin
- `bin/__pycache__/` / `*.pyc` — never commit; `.gitignore` covers them and a
  republish strips any that slipped into a standalone repo.
