# New-laptop restore playbook

This playbook targets the current Arch Linux ARM/Asahi host. It is deliberately
architecture-specific: do not copy package or service assumptions from an x86
machine. The machine index and package files are the source of truth for the
sanitized state; private shell configuration remains in the operator's dotfiles
repository.

> Restore with an operator present. Stop for keyring unlock, account login,
> package-manager authentication, and any hardware-specific confirmation.

## 0. Guardrails

- Never write secrets, tokens, private keys, or keyring exports to git.
- Never edit `/usr/share/omarchy/`; use supported host configuration or a
  separately owned local clone.
- Prefer `omarchy pkg add` and the documented Asahi package families.
- Do not install GPU, firmware, or microcode packages that are not verified for
  the target hardware.
- Run `scripts/audit-live-plugins.py` before and after plugin changes.

## 1. Base system

1. Install the current Omarchy/Arch Linux ARM image with the Asahi kernel and
   matching firmware packages.
2. Create the operator account with the groups required by the desktop
   (`wheel`, input, and the groups required by the selected package manager).
3. Install and authenticate Tailscale if remote access is required. Keep the
   SSH daemon disabled; use Tailscale SSH only.
4. Sign in to 1Password and GitHub through their normal interactive flows. Do
   not paste credentials into this repository or an agent prompt.

## 2. Dotfiles and desktop configuration

Set a private checkout directory, then apply the operator's chezmoi repository:

```sh
export DOTFILES_DIR="${DOTFILES_DIR:-$HOME/src/dotfiles}"
chezmoi init --apply "git@github.com:duketopceo/dotfiles.git"
```

Review the generated plan before applying changes. The private repository owns
Hyprland, Omarchy shell, terminal, and user-service configuration; this
repository owns only the sanitized machine map and the plugin umbrella.

## 3. Packages

Install the explicit package list with the host-supported package manager:

```sh
xargs -a machine/packages-explicit.txt -r omarchy pkg add
```

Review `machine/packages-foreign.txt` before installing AUR or other foreign
packages. The current host uses the Asahi kernel, PipeWire/WirePlumber, BlueZ,
UPower, and Apple audio services. Do not add desktop packages for a different
GPU architecture unless the operator explicitly changes the hardware target.

## 4. Toolchain

Restore the pinned tools from `machine/mise.toml` rather than copying binaries
from the old machine:

```sh
mise install
mise upgrade
```

Install any project-local tools from their declared package manager and verify
versions before use. Do not copy dropped AppImages or user-specific binaries
into this repository.

## 5. Host services

Enable only the services represented in `machine/INDEX.md` and verify them
after login:

- PipeWire, WirePlumber, and Asahi microphone/audio services
- BlueZ integration for Bluetooth devices
- desktop portals and Hyprland session services
- EasyEffects when the operator wants the DSP layer
- Hyprmoncfg for managed display layouts
- Voxtype is the default voice owner; enable `voxtype.service` and its bar
  control only after the operator confirms the capture/privacy policy.
- Dim remains an opt-in alternative and must not run at the same time as
  Voxtype while both claim the microphone.

A failed optional service is a degraded state; it must not cause restore to
invent credentials or enable a second data collector.

## 6. Owned plugins

Clone this public authoring repository into an operator-selected directory and
run the local installer in development-link mode:

```sh
export PLUGIN_REPO="${PLUGIN_REPO:-$HOME/src/omarchy-plugins}"
git clone https://github.com/duketopceo/omarchy-plugins.git "$PLUGIN_REPO"
cd "$PLUGIN_REPO"
./scripts/install.sh --link
```

The installer keeps development links distinct from release copies. For a
release, use the validated copy path and run the manifest and contract checks
before publishing a standalone plugin repository.

## 7. Marketplace and external plugins

Use the remotes recorded in `machine/plugins.json`:

```sh
omarchy plugin add <git-url> --enable --yes
```

Keep ownership and update paths independent. A local checkout, a disabled
clone, and a hosted tray widget are different states; do not infer that an
absent direct bar entry means the surface is unused.

Before applying the sanitized bar layout, run the read-only migration plan:

```sh
python3 scripts/plan-surface-migration.py --format markdown
```

Apply the sanitized bar layout from `machine/bar-layout.json` and the enabled
plugin list from `machine/plugins.json`, then ask the host to rescan:

```sh
omarchy-shell shell rescanPlugins
```

Do not hand-edit host-owned registry state. If a backup directory shadows an
installed plugin, stop and use the reversible installer migration.

## 8. Secrets and private data

OmaSeal is the canonical secret-management surface. Unlock it interactively and
confirm that consumers can resolve keys at use time. The inventory records
whether a keyring is available, never a key or token value.

Before enabling screen, audio, clipboard, calendar, finance, weather, or
message surfaces, review their egress and retention policy in
`docs/DATA-LIFECYCLE.md`. Do not restore or delete private data as an implicit
part of a plugin migration.

## 9. Verification

```sh
omarchy version
uname -m
hyprctl monitors
omarchy-shell shell listPlugins
python3 scripts/audit-live-plugins.py --format json
python3 scripts/check-host-integration.py --format markdown
python3 scripts/validate-manifests.py
```

Check the bar, tray-hosted widgets, audio devices, Bluetooth state, display
layout, suspend/resume behavior, and service health. Record any unavailable
capability as unavailable; do not replace a failed probe with a fabricated
value.

## Stop and ask the operator for

- keyring or 1Password unlock
- Tailscale, GitHub, NordVPN, or other account login
- package-manager or firmware authorization
- confirmation before enabling a new screen/audio/voice capture surface
- confirmation before any destructive cleanup of user data
