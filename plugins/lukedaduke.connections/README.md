# Connections

A compact Omarchy bar widget that shows Bluetooth and Wi-Fi state side by side — dual icons with per-radio toggle controls and status-at-a-glance coloring.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-connections
omarchy plugin enable lukedaduke.connections
```

## Features

- Combined Bluetooth + Wi-Fi indicator for the bar
- One-click radio toggles
- Reuses Omarchy's stock bluetooth and network panel UIs for dropdowns

## Remove

```bash
omarchy plugin disable lukedaduke.connections
omarchy plugin remove lukedaduke.connections
```

## Notes

This plugin embeds the stock Omarchy shell panels
(`/usr/share/omarchy/shell/plugins/panels/bluetooth|network/Panel.qml`) for
its dropdown views, so it requires a stock Omarchy install. It spawns no
processes of its own.

MIT — see [LICENSE](LICENSE).
