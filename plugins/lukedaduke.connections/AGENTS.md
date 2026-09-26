# AGENTS.md — Connections (`lukedaduke.connections`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Compact bar widget showing Bluetooth and Wi-Fi state side by side: dual icons
with per-radio toggle controls and at-a-glance status coloring. Icons dim when a
radio is off or missing. The dropdowns reuse Omarchy's own stock Bluetooth and
network panel UIs rather than reimplementing them.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/lukedaduke.connections/`. `scripts/publish.sh` runs `git subtree split`
and fast-forwards this repo's `main`. **A commit made directly here is deleted on
the next publish.** Make the change in the umbrella, then
`scripts/publish.sh connections`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["bar-widget"]` |
| `BarWidget.qml` | The entire widget. Single file |
| `preview.png` | Marketplace listing image |

**This is the smallest plugin in the family: one QML file, no `bin/`, no Python,
no assets.** Its umbrella test coverage is static analysis of the QML text, not
runtime behavior.

## Runtime Contract

- **No build step.** Nothing to compile. `manifest.json` must stay valid JSON.
- **QML cannot be checked outside Omarchy.** `BarWidget.qml` imports `Quickshell`,
  `Quickshell.Bluetooth`, `Quickshell.Networking`, `qs.Commons`, and `qs.Ui`. The
  `Quickshell.*` and `qs.*` modules are provided by the host shell at runtime and
  are absent from a plain checkout, so `qmllint` reports unresolvable imports.
  Not a bug.
- This plugin talks to BlueZ and NetworkManager **through the Quickshell APIs
  directly**, not by shelling out. There is no helper process and no JSON to
  bound.
- `moduleName` must equal the manifest `id` (`lukedaduke.connections`). Unlike the
  other plugins here it sets no `ipcTarget` — it has no IPC surface.
- A missing adapter or absent radio is a normal state, not an error. The icon
  dims. Do not convert that into a thrown error or a warning banner.

## Validation

No test suite in this repo. The umbrella covers it in `tests/test_connections.py`
(9 tests), which **parses `BarWidget.qml` as text** rather than running it. From
the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/test_connections.py -q
```

Those tests are load-bearing and encode real constraints. They assert the
Bluetooth dimming binds actual adapter state, the Wi-Fi dimming binds actual
networking state, there is no dead anchor injection, the `Loader`s fill their bar
buttons and warn on error, the panel sources are the stock Omarchy paths, the
README carries the stock-widget IPC warning, and the stock panels still expose
the widget contract. **Editing `BarWidget.qml` without reading
`tests/test_connections.py` first will likely fail CI.**

These tests are platform-independent and pass on macOS.

**They verify structure, not behavior.** Real verification is still manual and
mandatory: on Linux with the plugin enabled, confirm both icons render, that
toggling each radio actually changes BlueZ / NetworkManager state, and that the
dropdowns open Omarchy's stock panels. Say so explicitly in any PR — do not imply
CI covered the runtime behavior.

## Runtime Requirements

- Linux with BlueZ and NetworkManager running
- A Bluetooth adapter is optional; the widget is designed to render without one

## Conventions

- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded palette hex.
- Reuse the stock Omarchy panel UIs for the dropdowns. Do not fork them locally.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.
