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

## Learned User Preferences

- Do not use fast Composer models for ce-plan, ce-work, or review; use normal tiers (e.g. Grok 4.7 medium).
- Clipboard UX target is Paste-like polish on Omarchy (dark, `qs.Commons`), not stock CopyQ GUI or a CopyQ fork.
- Do not fork or patch the CopyQ package for UI; integrate via `lukedaduke.copyq` Quickshell overlay and `bin/` helpers.
- Keep SUPER+C and SUPER+V as Omarchy universal copy/paste; the CopyQ plugin owns history chords only.
- Local clipboard history and agent MCP access matter more than cross-device sync.
- Test the overlay before reconfiguring CopyQ native UI or hotkeys to mimic Paste.
- pixel-tycoon, reactor-sim, and similar game repos are not bartlett work and must not appear in bartlett agent memory.
- When implementing an attached CE plan, do not edit the plan file; use the todos already created.

## Learned Workspace Facts

- This worktree (`~/.local/share/worktrees/omarchy-copyq-plugin`) authors `plugins/lukedaduke.copyq`; live dev uses `scripts/install.sh --link`.
- Stock CopyQ owns capture, tabs (`&clipboard`, `Pins`), and storage; the plugin is overlay plus helpers only.
- `copyq-mcp` is the supported AI clipboard surface (paired with CopyQ in Cursor MCP config).
- Hypr history chords: SUPER+SHIFT+V opens the cursor overlay and SUPER+ALT+V runs silent `copyq next`. SUPER+CTRL+V is planned to summon the center overlay (`omarchy-shell shell summon lukedaduke.copyq`) but the stash-canonical bind in `~/.local/share/machine/lukekimball/bindings.lua` still runs `copyq toggle`; that file is outside this repo.
- Ship path: merge on `duketopceo/omarchy-plugins`, then `scripts/publish.sh lukedaduke.copyq` for `omarchy plugin add`.
- Overlay summon: `omarchy-shell shell summon|hide lukedaduke.copyq`; cursor mode via `{"mode":"cursor"}`.
- CopyQ-specific agent contract: `plugins/lukedaduke.copyq/AGENTS.md` (edits belong in the umbrella; subtree publish overwrites the public repo).
- Continual-learning transcript index: `.cursor/hooks/state/continual-learning-index.json`.
