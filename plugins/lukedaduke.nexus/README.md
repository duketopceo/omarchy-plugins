<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/lockup-dark.svg">
    <img src="assets/brand/lockup.svg" alt="Hardware Nexus" height="48">
  </picture>
</p>

<p align="center"><strong>A live hardware topology map of USB, Bluetooth, network and storage, from the Omarchy bar.</strong></p>

<!-- Logo is a proposal pending owner sign-off. TODO: replace preview.png (a listing mock-up) with a real screenshot from a live Omarchy session. -->

A native Omarchy bar widget that opens a live hardware topology radar: USB bus,
Bluetooth mesh, network interfaces and VPNs, NVMe/storage, and internal
silicon — rendered as an animated interconnect map.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-nexus
omarchy plugin enable lukedaduke.nexus
```

## Features

- Animated radar panel of every wired, wireless, and internal connection
- Tabs: overview, USB, Bluetooth, network, storage
- USB device identification with a known-hardware dictionary plus
  class-based fallback naming (hubs, input, cameras, audio, storage)
- Bluetooth connected-device list via `bluetoothctl`
- Network interfaces and addresses via `ip -j addr`
- Block devices, models, transports, and mountpoints via `lsblk -J`
- All probing is read-only: `/sys/bus/usb/devices` and local CLI output only

## Usage

- **Click** the bar widget — open the panel
- **Esc** — close the panel

## Requirements

- `python3`
- `bluetoothctl` (package `bluez-utils`) — optional, Bluetooth tab is empty without it
- `ip` (package `iproute2`)
- `lsblk` (package `util-linux`)
- Readable `/sys/bus/usb/devices` (default on Linux)

## Removal

```bash
omarchy plugin remove lukedaduke.nexus
```

## How it works

```mermaid
flowchart LR
  P[Panel.qml] --> H[bin/probe_nexus.py]
  H --> U[/sys/bus/usb/devices]
  H --> B[bluetoothctl]
  H --> N[ip -j addr]
  H --> L[lsblk -J]
  H -->|bounded JSON| P
```

## Status and roadmap

Proposed program roadmap with difficulty, feasibility and simpler alternatives: [ROADMAP.md](ROADMAP.md). Design direction: [DESIGN.md](DESIGN.md). Landscape notes: [docs/research/2026-10-10-landscape.md](docs/research/2026-10-10-landscape.md).

## Contributing

This repository is the published mirror of [`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) (`plugins/lukedaduke.nexus/`). Open issues here; send changes to the umbrella, because a direct commit here is overwritten by the next publish. Read `AGENTS.md` first.

## License

MIT
