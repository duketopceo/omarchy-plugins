# AGENTS.md — CopyQ (`lukedaduke.copyq`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Paste-like Omarchy Quickshell overlay for clipboard history. Stock CopyQ owns
capture, history storage, and MCP. This plugin is the theme-native picker:
centered history, at-cursor menu, pins, and image thumbs.

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
| `bin/copyq-list.py` | Pins + clipboard JSON (text/image) |
| `bin/copyq-activate.sh` | `select` + optional `paste` by index/tab |
| `bin/copyq-remove.sh` | Remove by index/tab |
| `bin/copyq-pin.sh` | Copy row into CopyQ `Pins` tab |

## Runtime Contract

- Overlay kind: summon/hide via `omarchy-shell shell summon|hide lukedaduke.copyq`.
- Cursor mode: `summon lukedaduke.copyq '{"mode":"cursor"}'`.
- Theme only through `qs.Commons` `Color` / `Style` — no hardcoded theme hex.
- Fixed `/usr/bin/copyq` and `/usr/bin/python3` (helpers honor `COPYQ_BIN`
  for tests; activate also honors `WTYPE_BIN`, `HYPRCTL_BIN`, `JQ_BIN`,
  `COPYQ_PASTE_DELAY`).
- `copyq-list.py` collects rows with ONE `copyq eval` — never loop `copyq
  read`/`count` per row; that costs seconds. The eval script must contain no
  backslash escapes (`copyq eval` unescapes its argument): use
  `String.fromCharCode` and `charCodeAt` instead of `\n`, `\s`, `\uXXXX`.
- Every `Text` that binds clip or status strings uses `textFormat: Text.PlainText`.
- Dismiss goes through `shell.hide(manifest.id)`. Do not call `copyq toggle` /
  `copyq show` from the overlay.
- Clipboard tab is `&clipboard`; pins live in tab `Pins`.

## Agent Instructions

- Do not fork or patch the CopyQ package for UI.
- Do not add a second clipboard watcher.
- Keep SUPER+C / SUPER+V as Omarchy universal copy/paste; this plugin owns history chords only.
- Keep SUPER+ALT+V silent (`copyq next`) — no toast.
