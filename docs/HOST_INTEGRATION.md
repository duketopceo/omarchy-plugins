# Host integration health

`check-host-integration.py` is a read-only health check for the host surfaces
that the plugin estate depends on. It uses fixed executable paths, bounded
subprocesses, a minimal environment, and never copies raw command output into
its report.

## Checked surfaces

- **Audio:** PipeWire, WirePlumber, `wpctl`, and optional EasyEffects.
- **Bluetooth:** `bluetoothctl` adapter state and the user Bluetooth bridge.
- **Display:** Hyprland monitor state and optional Hyprmoncfg management.
- **Input:** presence of accessible input-device entries.

A missing optional dependency produces `degraded` with a reason; it does not
make basic audio, Bluetooth, or display controls disappear. The report never
contains credentials, device serials, command output, or filesystem paths.

## Usage

```sh
python3 scripts/check-host-integration.py
python3 scripts/check-host-integration.py --format markdown
python3 scripts/check-host-integration.py --strict
```

`--strict` exits non-zero when any surface is degraded. The default command is
report-only and is suitable for the live inventory and restore checklist.

## Ownership

The owned `lukedaduke.connections` widget embeds the host Bluetooth and
Network panels but does not copy or edit host-owned Omarchy source. Fixes for
external audio-control, Omaphones, and Hyprmoncfg surfaces remain upstream or
configuration work; record their state in
`docs/reviews/active-plugin-contract.md`.
