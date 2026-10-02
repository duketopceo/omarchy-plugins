# AGENTS.md — Hardware Nexus (`lukedaduke.nexus`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Bar widget that opens a live hardware topology radar: USB bus, Bluetooth mesh,
network interfaces and VPNs, NVMe/storage, and internal silicon, rendered as an
animated interconnect map. Tabs: overview, USB, Bluetooth, network, storage.
USB devices are matched against a known-hardware dictionary for friendly names.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/lukedaduke.nexus/`. `scripts/publish.sh` runs `git subtree split` and
fast-forwards this repo's `main`. **A commit made directly here is deleted on the
next publish.** Make the change in the umbrella, then `scripts/publish.sh nexus`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["bar-widget"]` |
| `Panel.qml` | Bar text + dropdown, animated radar. ~380 lines |
| `bin/probe_nexus.py` | Reads sysfs/BlueZ/route state, emits bounded JSON |
| `preview.png` | Marketplace listing image |

The panel execs the helper with the absolute interpreter `/usr/bin/python3`.

## Runtime Contract

- **No build step.** Nothing to compile. `manifest.json` must stay valid JSON.
- **QML cannot be checked outside Omarchy.** `Panel.qml` imports `Quickshell`,
  `Quickshell.Io`, `QtQuick.Layouts`, `qs.Commons`, and `qs.Ui`. The `qs.*`
  modules come from the host shell at runtime and are missing in a plain
  checkout, so `qmllint` reports unresolvable imports. Not a bug.
- `moduleName` and `ipcTarget` must both equal the manifest `id`
  (`lukedaduke.nexus`).
- **Every probe is optional by design.** Missing `bluetoothctl`, an absent
  `/sys/bus/usb`, or a down radio must yield an empty or greyed tab, never an
  error state or a crash. This plugin is expected to run on varied hardware; a
  probe that hard-fails on a missing tool is a bug.

## Validation

There is no test suite in this repo. From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/ -q          # includes tests/test_probe_nexus.py
```

Standalone:

```bash
python3 -m py_compile bin/*.py
```

The umbrella suite requires Linux (GNU `head -z`, `/proc/meminfo`), so on macOS
expect unrelated failures from `test_agents.py` / `test_fan_stats.py` while
`test_probe_nexus.py` passes.

Real verification is on Linux with the plugin enabled: each tab populates on a
laptop that has the corresponding hardware, and a tab degrades cleanly when the
tooling is absent.

## Runtime Requirements

- `python3`
- `ip` (`iproute2`) — network interfaces, routes, VPN
- `lsblk` (`util-linux`) — storage
- `bluetoothctl` (`bluez-utils`) — optional; the Bluetooth tab is empty without it
- Readable `/sys/bus/usb/devices` (default on Linux)

## Conventions

- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded palette hex.
- Keep the helper stdlib-only; no package manifest exists here to carry a
  dependency.
- Keep child `PATH` pinned to a fixed safe list and exec helpers by absolute
  path, so a `PATH`-preceding shadow binary cannot execute.
- Bound the helper's stdout — the QML side parses it.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.
