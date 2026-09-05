# Hardware Nexus

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

## License

MIT
