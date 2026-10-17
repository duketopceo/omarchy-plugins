<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/wordmark-dark.svg">
    <img src="assets/brand/wordmark.svg" alt="omarchy-power" height="48">
  </picture>
</p>

# Power

An Omarchy bar widget for laptop power: live battery status, a historical ASCII charge graph, top resource consumers, and power-profile switching.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-power
omarchy plugin enable lukedaduke.power
```

## Features

- Battery percentage/state from `omarchy-battery-status`
- ASCII charge-history graph sampled by `battery_helper.py` into
  `~/.local/state/omarchy/battery_history.json`
- Top CPU/memory consumers
- Power profiles via `omarchy-powerprofiles-list` /
  `omarchy-powerprofiles-set` (persists under
  `~/.local/state/omarchy/powerprofiles`)
- Exposes an `omarchy.power` IPC target for keybind-driven profile actions

## External dependencies

- `power-profiles-daemon` + the stock `omarchy-*` helper commands

## Remove

```bash
omarchy plugin disable lukedaduke.power
omarchy plugin remove lukedaduke.power
```

MIT — see [LICENSE](LICENSE).

## Status and design

- Roadmap: [ROADMAP.md](ROADMAP.md)
- Design direction (Pilot Light, shared by the Omarchy plugin family): [DESIGN.md](DESIGN.md)
- Landscape research: [docs/research/2026-10-11-landscape.md](docs/research/2026-10-11-landscape.md)
- Authoring catalog and shared rules: https://github.com/duketopceo/omarchy-plugins

## Contributing

This repository is the published mirror of [`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) (`plugins/lukedaduke.power/`). Send changes to the umbrella; a direct commit here is overwritten by the next publish.
