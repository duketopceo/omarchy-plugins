# AGENTS.md — omarchy-plugins

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Luke's personal Omarchy shell plugins (Quickshell QML) for the laptop bar: fan control, power and battery history, a hardware topology radar, an OLED nightstand overlay, and the Perplexity tool trio (bumblebee, numbat, pplx) plus neo. connections, ticker and agents are retired (notice-only stubs). Source of truth for `lukedaduke.*` plugins. Live install is a copy from `main` (`scripts/install.sh --copy`); develop with `--link` from a separate worktree.

## Key Files

- `plugins/<id>/manifest.json` — Omarchy plugin contract (id, kinds, entryPoints)
- `plugins/<id>/Panel.qml` — bar widget + dropdown
- `plugins/<id>/bin/` — helpers the panel execs
- `scripts/install.sh` — `--link` or `--copy` into Omarchy plugin dir
- `scripts/audit-live-plugins.py` — read-only, sanitized live/fixture inventory
- `scripts/validate-manifests.py` — schema check
- `catalog.json` — machine-readable plugin list
- `machine/` — laptop inventory and restore playbook (no secrets)

## Current Status

- [x] In development
- [x] On GitHub (`duketopceo/omarchy-plugins`, public). Not first-party Omarchy.
- [ ] Production traffic (local desktop only)

## Active Issues / Known State

- `omarchy plugin add` clones a whole git repo with `manifest.json` at root. This umbrella repo is the authoring catalog; each plugin dir subtree-pushes to its own public repo via `scripts/publish.sh` (see `docs/UPSTREAM.md` for the inbound/outbound sync model).
- Bar currently uses `akitaonrails.ai-usagebar` for usage, not `lukedaduke.agents`.
- `lukedaduke.tailscale` is an unused stock clone and is not in this repo.

## Agent Instructions (repo-specific)

- Never edit `/usr/share/omarchy/`.
- Do not vendor third-party Omarchy marketplace plugins here.
- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded Dracula hex.
- Helpers live in `plugins/<id>/bin/`, not `~/.local/bin`.
- Default: follow duketopceo/luke-agents for all standards.


## Code graph index (optional accelerator)

This repo may be indexed by `codebase-memory-mcp` (CBM) on an agent's local machine — `.codebase-memory/` is gitignored. If your harness exposes CBM tools (`search_graph`, `trace_path`, `get_architecture`, `detect_changes`), prefer them for structural questions — symbol lookup, caller/callee traces, impact analysis — instead of grep/read loops. Reindex after large refactors (`index_repository`); treat `.codebase-memory/graph.db.zst` as a local cache artifact, never commit it.
