# Connections

A compact Omarchy bar widget that shows Bluetooth and Wi-Fi state side by side — dual icons with per-radio toggle controls and status-at-a-glance coloring.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-connections
omarchy plugin enable lukedaduke.connections
```

## Features

- Combined Bluetooth + Wi-Fi indicator for the bar
- Icons dim when a radio is off or missing (BlueZ adapter state / NetworkManager
  Wi-Fi state) — status at a glance
- One-click radio toggles
- Reuses Omarchy's stock bluetooth and network panel UIs for dropdowns,
  anchored under their own icons

## Remove

```bash
omarchy plugin disable lukedaduke.connections
omarchy plugin remove lukedaduke.connections
```

## Notes

This plugin embeds the stock Omarchy shell panels for its dropdown views, so it
requires a stock Omarchy install. It resolves the host root from
`OMARCHY_PATH` and falls back to the packaged `/usr/share/omarchy` location.
If either panel cannot load, the corresponding icon is dimmed and its tooltip
reports the panel as unavailable instead of presenting a false control. It
spawns no processes of its own.

Run the read-only host check when a radio, panel, or permission appears broken:

```bash
python3 scripts/check-host-integration.py --format markdown
```

**Disable the stock Bluetooth/Network widgets.** The embedded panels register
IPC handlers on `omarchy.bluetooth` and `omarchy.network`. If the stock
widgets stay in your bar layout, both instances compete for the same IPC
target — first registration wins, so calls route unpredictably — and each panel
runs its own service subscriptions. Remove the `omarchy.bluetooth` and
`omarchy.network` entries from the bar layout; this widget replaces them.

Because both full stock panels stay loaded behind the icons, this widget is
heavier than two plain icon buttons — the tradeoff for reusing their
dropdowns, keyboard navigation, and radio toggles.

## Data and privacy

The widget reads only Bluetooth and network state from the host panels. It
does not log device names, addresses, credentials, or network payloads. The
host integration checker records status categories, not raw command output.

MIT — see [LICENSE](LICENSE).
