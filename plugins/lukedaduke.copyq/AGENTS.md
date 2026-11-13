# AGENTS.md — CopyQ (`lukedaduke.copyq`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Paste-like Omarchy Quickshell overlay for clipboard history. Stock CopyQ owns
capture, history storage, and MCP. This plugin is the theme-native picker:
centered history, at-cursor menu, pins, image thumbs, and a ~30m Fernet hot
vault for API-key-shaped clips.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/lukedaduke.copyq/`. `scripts/publish.sh` runs `git subtree split` and
fast-forwards this repo's `main`. **A commit made directly here is deleted on the
next publish.** Make the change in the umbrella, then
`scripts/publish.sh lukedaduke.copyq`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["overlay"]`, `entryPoints.overlay` |
| `Overlay.qml` | Picker UI (center + cursor modes) |
| `bin/copyq-list.py` | Pins + clipboard JSON; harvests key-shaped clips into hot vault |
| `bin/copyq_hotkeys.py` | Fernet vault under `$XDG_RUNTIME_DIR` (~30m TTL); list/activate/drop |
| `bin/copyq-activate.sh` | `select` + optional `paste` by index/tab, or `--hot-id` |
| `bin/copyq-remove.sh` | Remove by index/tab, or drop vault entry via `--hot-id` |
| `bin/copyq-pin.sh` | Pin clipboard row into `Pins`, or unpin when tab is `Pins` |

## Runtime Contract

- Overlay kind: summon/hide via `omarchy-shell shell summon|hide lukedaduke.copyq`.
- Cursor mode: `summon lukedaduke.copyq '{"mode":"cursor"}'`.
- Theme only through `qs.Commons` `Color` / `Style` — no hardcoded theme hex.
- Fixed `/usr/bin/copyq` and `/usr/bin/python3` (helpers honor `COPYQ_BIN` for tests).
- Every `Text` that binds clip or status strings uses `textFormat: Text.PlainText`.
- Dismiss goes through `shell.hide(manifest.id)`. Do not call `copyq toggle` /
  `copyq show` from the overlay.
- Clipboard tab is `&clipboard`; pins live in tab `Pins`.

## Agent Instructions

- Do not fork or patch the CopyQ package for UI.
- Do not add a second clipboard watcher.
- Keep SUPER+C / SUPER+V as Omarchy universal copy/paste; this plugin owns history chords only.
- Keep SUPER+ALT+V silent (`copyq next`) — no toast.
