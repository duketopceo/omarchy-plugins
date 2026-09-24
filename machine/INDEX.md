# Machine index — `omarchy` laptop

Snapshot date: 2026-09-23.

This is a **restore map**, not a secret store. Private shell configuration lives
in the operator's chezmoi repository; this file contains only architecture,
service, package-family, and plugin metadata. Never copy credentials, tokens,
private keys, keyring entries, machine IDs, or private network addresses here.

## Identity

| Field | Value |
|---|---|
| Hostname | `omarchy` |
| OS | Arch Linux ARM / Omarchy |
| Architecture | `aarch64` |
| Kernel | `linux-asahi` rolling kernel (`7.1.x`) |
| Hardware | Apple MacBook Pro (`MacBookPro18,2`, M1 Max) |
| Memory | 62 GiB unified memory |
| Graphics | Asahi `apple-agx` / `t6001`; integrated GPU only |
| Display | `eDP-1` preferred mode, scale `1.25` |
| Filesystem | Btrfs root with Snapper |
| Default browser | Chromium; Brave is installed |
| Theme | Miasma |

## Source-of-truth repositories

| Repository | Visibility | Role |
|---|---|---|
| `duketopceo/omarchy-plugins` | public | Umbrella authoring tree, owned plugins, machine index |
| `duketopceo/dotfiles` | private | Hyprland, Omarchy shell, terminals, and user services |
| `duketopceo/luke-agents` | private | Agent standards and skills |
| `duketopceo/dayflow-linux` | private | Dayflow source checkout used by the external-owner handoff |

## Networking policy

- Tailscale is the remote-access backbone; Tailscale SSH is used and `sshd` is
  not enabled.
- NordVPN/NordLynx is installed. Meshnet remains disabled.
- UFW defaults to deny for incoming and forwarded traffic.
- LocalSend and local development services bind to loopback unless explicitly
  changed. Do not publish ports through Tailscale without a documented need.
- No addresses, account identifiers, or machine IDs belong in this repository.

## Omarchy desktop

- Hyprland configuration is managed by the private dotfiles repository under
  `$HOME/.config/hypr/`.
- Shell configuration is `$HOME/.config/omarchy/shell.json`; idle and bar state
  are represented by the sanitized files in `machine/`.
- First-party plugins install with `./scripts/install.sh --link` during local
  development. Marketplace plugins retain their own remotes and ownership.
- The custom tray hosts `jankeesvw.herdr` and `lukedaduke.nexus`; hosted widgets
  are not redundant with the direct bar layout.
- OmaSeal is the intended canonical secret-management surface. This index does
  not contain account names, keyring labels, or secret values.

## Toolchain

See `machine/mise.toml`, `machine/packages-explicit.txt`, and
`machine/packages-foreign.txt` for the current package/tool inventory. The
machine uses `quickshell`, Python helpers, PipeWire/WirePlumber, BlueZ, UPower,
Asahi audio, and the Asahi kernel family. Do not restore packages for a
separate discrete GPU or other x86-only package families on this host unless
a separately verified target requires them.

Important tools include `git`, `gh`, `jq`, `mise`, `uv`, and the pinned editor
and agent CLIs listed in `machine/mise.toml`. Optional applications are restored
from their package sources, not copied from an old machine.

## Services

The following user-service families are part of the current desktop contract:

- `pipewire.service`, `pipewire-pulse.service`, and `wireplumber.service`
- `omarchy-asahi-mic.service` and Asahi audio support
- `bluez` through the `bt-agent.service` integration
- `easyeffects.service` (optional DSP layer; failure is degraded, not fatal)
- `hyprmoncfgd.service` for monitor management
- `dayflow-capture.service` and `dimd.service` for explicitly configured
  capture/voice surfaces; Dim is opt-in
- `voxtype.service` as the default voice owner
- `omarchy-sleep-lock.service`, desktop portals, and Hyprland session services

The inventory is descriptive. The live audit records which services are
running and healthy without copying journal contents or credentials. Run
`python3 scripts/check-host-integration.py --format markdown` for the current
audio, Bluetooth, display, and input capability report.

## Plugin policy

- Host-owned Omarchy plugins are not edited in this repository.
- Owned `lukedaduke.*` and `io.github.duketopceo.*` plugins publish from their
  standalone repositories through the umbrella workflow.
- Third-party plugins remain independently owned; follow-up fixes are recorded
  in `docs/reviews/active-plugin-estate.md` rather than vendored here.
- Replacement surfaces have one owner for each IPC target, service, hotkey, and
  data source.

## Restore entry points

1. Read `machine/RESTORE.md`.
2. Install the base Arch Linux ARM/Asahi system and desktop services.
3. Apply the sanitized bar/plugin state from `machine/bar-layout.json` and
   `machine/plugins.json`.
4. Run the read-only inventory before changing live plugin state.
5. Ask the operator to unlock or authenticate any keyring, account, or package
   manager interaction; never invent credentials during restore.

## Not in this index

Secrets, Tailscale addresses, machine ID, SSH private keys, wallet keys, API
tokens, AppFlowy credentials, NordVPN tokens, browser profiles, message history,
clipboard history, and private dotfile contents.
