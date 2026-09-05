# New-laptop restore playbook

Use this with an AI that has GitHub access to `duketopceo/omarchy-plugins`, `duketopceo/dotfiles`, and `duketopceo/luke-agents`.

Prompt to paste:

> Restore my Omarchy laptop from `duketopceo/omarchy-plugins` `machine/INDEX.md` and `machine/RESTORE.md`. Pull actual config from private `duketopceo/dotfiles` via chezmoi. Do not invent secrets. Stop and ask for 1Password / Tailscale / GitHub auth when needed.

## 0. Guardrails

- Never write secrets to git.
- Never edit `/usr/share/omarchy/`.
- Prefer `omarchy pkg add` / `yay` over raw `makepkg`.
- `sudo` on this distro is fingerprint-first; an agent without a TTY cannot auth.

## 1. Base OS

1. Install Omarchy (Arch/Hyprland). Target ~4.0.x.
2. Create user `lukedaduke`, groups: `wheel`, `docker`.
3. Install Tailscale. Log in. Enable Tailscale SSH. `--accept-routes`. Do **not** enable sshd on port 22.
4. Sign into 1Password. `op` CLI.
5. Sign into GitHub (`gh auth login`). Need access to private `dotfiles` and `luke-agents`.

## 2. Dotfiles

```bash
chezmoi init --apply git@github.com:duketopceo/dotfiles.git
```

This is the Hyprland / Omarchy shell / terminal / user-timer source. If chezmoi is missing, grab the binary first (`omarchy pkg add chezmoi` or the release in `~/.local/bin` historically).

## 3. Packages

```bash
# explicit package names
xargs -a machine/packages-explicit.txt -r omarchy pkg add
```

Foreign/AUR names are in `machine/packages-foreign.txt` (`brave-bin`, `claude-desktop`, `nordvpn-gui-bin`, `slack-desktop`, `snapd`, `termius`). Use `omarchy pkg aur add` / `yay`. Skip anything the new hardware does not need (NVIDIA stack on a non-Nvidia box).

Precision 5560 notes: `nvidia-open-dkms`, `intel-media-driver`, `fprintd`, `thermald`.

## 4. Toolchain

```bash
cp machine/mise.toml ~/.config/mise/config.toml
mise install
mise upgrade

uv tool install a0
uv tool install browser-use
uv tool install hermes-agent
```

Install node-global tools after mise node is on PATH: `@devcontainers/cli`, `agent-browser`, `devin-sdk-cli-linux-x64`, `@railway/cli`.

Cargo: `ast-grep`, `cargo-zigbuild`. Build `kurultai` from `duketopceo/kurultai` if needed.

Large CLIs historically dropped into `~/.local/bin` (not pacman): Factory `agy`, Orca `ori` + `orca.AppImage`, BrowserOS AppImage, ActivityWatch. Re-download current releases; do not copy stale binaries from this index.

## 5. First-party plugins (this repo)

```bash
git clone git@github.com:duketopceo/omarchy-plugins.git ~/Documents/github/personal/omarchy-plugins
cd ~/Documents/github/personal/omarchy-plugins
./scripts/install.sh --link
```

## 6. Marketplace plugins

For each `git` URL in `machine/plugins.json` → `marketplace`:

```bash
omarchy plugin add <git-url> --enable --yes
```

Then restore bar layout from `machine/bar-layout.json` into `~/.config/omarchy/shell.json` (`bar` + `idle` + `disabledPlugins`). `omarchy-shell shell rescanPlugins`.

Keep stock `omarchy.tailscale` on the bar (do not replace with the unused `lukedaduke.tailscale` clone unless asked).

## 7. Skills

Clone private `luke-agents`. Symlink `SKILLS/` into `~/.agents/skills`, `~/.claude/skills`, `~/.grok/skills`. Add bartlett-agents `ce-*` skills the same way if this is a work machine.

## 8. Theme / desktop

```bash
omarchy theme set Miasma
```

Copy custom theme `firmitas-utilitas-venustas` from the old `~/.config/omarchy/themes/` if it is not in chezmoi.

Idle: screensaver 300s, lock 600s.

## 9. Network extras

- NordVPN: install, allowlist `100.64.0.0/10`, Meshnet **off**.
- UFW: default deny in/forward. LocalSend 53317. No sshd rule.
- Voxtype: user service `voxtype.service` + plugin `hancore.voxtype-enhance`.

## 10. Local dev

`devstack` compose: postgres 5432, redis 6379, minio 9100/9101 on localhost only. Source historically in `dotfiles/Work/devstack/`.

## 11. Verify

```bash
omarchy version
hyprctl monitors
omarchy-shell shell listPlugins | head
mise list
gh auth status
tailscale status
chezmoi doctor
```

Open the bar: calendar center, fan + ticker on the right, usagebar present.

## Stop and ask the human for

- 1Password vault unlock
- Tailscale login
- GitHub org access (work repos)
- NordVPN login
- Fingerprint enrollment (`omarchy setup security fingerprint`)
- NVIDIA vs Intel-only GPU choice if hardware differs
