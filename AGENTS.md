# AGENTS.md — omarchy-plugins

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Luke's personal Omarchy shell plugins (Quickshell QML) for the laptop bar: hardware/fan, market ticker, extra-provider agent usage, and an OLED nightstand overlay. Source of truth for `lukedaduke.*` plugins. Live install is a symlink into `~/.config/omarchy/plugins/`.

## Key Files

- `plugins/<id>/manifest.json` — Omarchy plugin contract (id, kinds, entryPoints)
- `plugins/<id>/Panel.qml` — bar widget + dropdown
- `plugins/<id>/bin/` — helpers the panel execs
- `scripts/install.sh` — `--link` or `--copy` into Omarchy plugin dir
- `scripts/validate-manifests.py` — schema check
- `catalog.json` — machine-readable plugin list
- `machine/` — laptop inventory and restore playbook (no secrets)

## Current Status

- [x] In development
- [x] On GitHub (`duketopceo/omarchy-plugins`, public). Not first-party Omarchy.
- [ ] Production traffic (local desktop only)

## Active Issues / Known State

- `omarchy plugin add` clones a whole git repo with `manifest.json` at root. This umbrella repo is the authoring catalog. Each plugin dir is already self-contained for a later split.
- Bar currently uses `akitaonrails.ai-usagebar` for usage, not `lukedaduke.agents`.
- `lukedaduke.tailscale` is an unused stock clone and is not in this repo.

## Agent Instructions (repo-specific)

- Never edit `/usr/share/omarchy/`.
- Do not vendor third-party Omarchy marketplace plugins here.
- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded Dracula hex.
- Helpers live in `plugins/<id>/bin/`, not `~/.local/bin`.
- Default: follow duketopceo/luke-agents for all standards.
