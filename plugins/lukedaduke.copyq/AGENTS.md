# AGENTS.md — CopyQ (`lukedaduke.copyq`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Omarchy Quickshell overlay for clipboard history. Stock CopyQ owns capture,
history storage, and MCP. This plugin is the theme-native picker only.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/lukedaduke.copyq/`. `scripts/publish.sh` runs `git subtree split` and
fast-forwards this repo's `main`. **A commit made directly here is deleted on the
next publish.** Make the change in the umbrella, then
`scripts/publish.sh copyq` (or the full id).

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["overlay"]`, `entryPoints.overlay` |
| `Overlay.qml` | Picker UI (search, list, activate) |
| `bin/copyq-list.py` | Emits CopyQ history as JSON |
| `bin/copyq-activate.sh` | `select` + optional `paste` by index |

## Runtime Contract

- Overlay kind: summon/hide via `omarchy-shell shell summon|hide lukedaduke.copyq`.
- Theme only through `qs.Commons` `Color` / `Style` — no hardcoded theme hex.
- Fixed `/usr/bin/copyq` and `/usr/bin/python3` paths; helpers must not resolve ambient PATH for CopyQ.
- Every `Text` that binds clip or status strings uses `textFormat: Text.PlainText`.
- Dismiss goes through `shell.hide(manifest.id)`. Do not call `copyq toggle` /
  `copyq show` from the overlay.

## Agent Instructions

- Do not fork or patch the CopyQ package for UI.
- Do not add a second clipboard watcher.
- Keep SUPER+C / SUPER+V as Omarchy universal copy/paste; this plugin owns the history chord only.
