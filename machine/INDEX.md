# Machine index — `omarchy` laptop

Snapshot date: 2026-09-02.

This is a **restore map**, not a secret store. Config files live in private `duketopceo/dotfiles` (chezmoi). Skills live in private `duketopceo/luke-agents` and work `bartlett-agents`. Never copy `.env`, `auth.json`, SSH private keys, or 1Password data into git.

## Identity

| Field | Value |
|---|---|
| Hostname | `omarchy` |
| OS | Omarchy 4.0.2 (Arch-like) |
| Kernel | 7.1.x (rolling) |
| Hardware | Dell Precision 5560 |
| User | `lukedaduke` (wheel, docker, nordvpn, wireshark) |
| Display | `eDP-1` preferred mode, scale **1.25** (see `~/.config/hypr/monitors.lua`) |
| Filesystem | Btrfs root + snapper |
| Default browser | Chromium (Brave also installed) |
| Theme | **Miasma** (custom theme dir also present: `firmitas-utilitas-venustas`) |

## Source-of-truth repos

| Repo | Visibility | Role |
|---|---|---|
| [duketopceo/omarchy-plugins](https://github.com/duketopceo/omarchy-plugins) | **private** | This catalog + first-party plugins + machine index |
| [duketopceo/dotfiles](https://github.com/duketopceo/dotfiles) | **private** | chezmoi: hypr, omarchy shell, terminals, systemd user timers, CLAUDE.md |
| [duketopceo/luke-agents](https://github.com/duketopceo/luke-agents) | **private** | AGENTS.md constitution + skills |
| bartlett-agents (work) | private | Extra `ce-*` skills |
| [duketopceo/kurultai](https://github.com/duketopceo/kurultai) | public | Local `kurultai` binary |

## Networking (policy, not addresses)

- Tailscale is the remote-access backbone. SSH daemon is off; Tailscale SSH only.
- NordVPN (NordLynx) installed. Keep Tailscale CGNAT (`100.64.0.0/10`) allowlisted. Nord Meshnet stays **disabled**.
- UFW: default deny incoming/forward. LocalSend 53317. Docker DNS 172.17.0.1:53. No port 22.
- 1Password + `op` CLI for secrets.

## Omarchy desktop

- Hyprland Lua config: `~/.config/hypr/{hyprland,bindings,monitors,looknfeel,input,autostart}.lua`
- Shell: `~/.config/omarchy/shell.json` — idle screensaver 300s, lock 600s
- Bar: top, transparent. Layout in `machine/bar-layout.json`
- Plugins: `machine/plugins.json`. First-party via `./scripts/install.sh --link`. Marketplace via `omarchy plugin add <git> --enable --yes`
- Custom theme overlay: `~/.config/omarchy/themes/firmitas-utilitas-venustas/`
- Hooks of note: `post-update.d/{install-voxtype,setup-fingerprint,setup-agent}.hook`

## Toolchain

See `machine/mise.toml`, `machine/packages-explicit.txt`, `machine/packages-foreign.txt`.

**mise:** claude, codex, copilot, crush, gemini, gh, grok (`npm:@xai-official/grok`), opencode, oh-my-pi, node 26.7.0, zig.

**uv tools:** a0, browser-use, hermes-agent.

**npm global:** `@devcontainers/cli`, `agent-browser`, `devin-sdk-cli-linux-x64`, `@railway/cli`, `@jsklan/devin-api-mcp`, `opencode-devin-plugin`. `@duketopceo/luke-agents` is a local link.

**cargo install:** ast-grep, cargo-zigbuild, kurultai (from source).

**Dropped binaries / AppImages** (not pacman): `agy`, `ori`, `orca.AppImage`, `herdr`, `chezmoi`, `fastpotify`, `ai-usagebar`, `hyprmoncfg`, `uv`/`uvx`, BrowserOS AppImage under `~/.local/opt/browseros`, ActivityWatch under `~/.local/opt/activitywatch`.

**Local PATH wrappers:** many `omarchy-*` helpers under `~/.local/bin`. Fan/ticker panels now call in-repo `plugins/*/bin` instead.

## Agent skills

`~/.agents/skills` (~93): luke-agents + bartlett-agents symlinks, plus stock Omarchy `omarchy` and `diagnose-crash`. Mirror into `~/.claude/skills` and `~/.grok/skills`.

## MCP (names only — auth is local)

Grok TUI on this machine has used: github, gmail, notion, tasks, finance, browseros, sequential-thinking, appflowy, hetzner, kurultai, robinhood. Optional/flaky: browser-use, pond, codebase-memory.

Browser harness: `~/.config/browser-harness/mcp/config.json` (`browser-use --mcp`).

## Services / timers

User: `mise-upgrade.timer`, `update-check.timer`, `activitywatch.service`, `voxtype.service`, `hyprmoncfgd.service`, `bt-agent.service`.

System: snapper-cleanup, snapper-timeline, paccache/docker-prune/fstrim/reflector typically via Omarchy (do not invent missing units).

Local dev: `devstack` → postgres 5432, redis 6379, minio 9100/9101 bound to 127.0.0.1.

## Ports to avoid

9000/9001 BrowserOS, 9200 BrowserOS MCP, 53317 LocalSend, 631 CUPS.

## What is NOT in this index

Secrets, Tailscale IPs, machine-id, SSH private keys, wallet keys, API tokens, AppFlowy credentials, NordVPN tokens.
