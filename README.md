# omarchy-plugins

<p align="center">
  <img src="docs/assets/social.png" alt="omarchy-plugins" width="640" />
</p>

> Luke's personal Omarchy bar plugins plus a laptop restore index. Not first-party Omarchy, and not a marketplace listing.

## Stack

- Quickshell / QML (Omarchy shell plugins)
- Python 3 helpers (hardware and power stats, weather, supply-chain and agent-activity scans, Perplexity search)
- Bash installer

## Local Setup

```bash
git clone https://github.com/duketopceo/omarchy-plugins
cd omarchy-plugins

uv run --with pytest pytest -q
python scripts/validate-manifests.py

# live install (hot-reload from this tree)
./scripts/install.sh --link

# release-style copy with generated artifacts excluded and validated
./scripts/install.sh --copy

# read-only live inventory (JSON by default; markdown with --format markdown)
python3 scripts/audit-live-plugins.py --no-git
```

The inventory distinguishes configured, direct-bar, tray-hosted, disabled, and
runtime-observed states without writing shell configuration or exposing secret
values. Live runs probe a fixed allowlist of user and system service units; use
`--fixture-root` for a host-independent audit. Legacy installer backups move
outside the discovery root and remain available for rollback. No `.env`
required. See `.env.example`.

## Plugins

| Id | What |
|---|---|
| `lukedaduke.fan` | RAM, CPU/GPU/NVMe temps, top processes, fan presets + custom curves |
| `lukedaduke.standby` | OLED nightstand overlay: clock, weather, markets, red tint, caffeine |
| `lukedaduke.copyq` | Omarchy clipboard overlay backed by stock CopyQ (theme-native picker) |
| `lukedaduke.nexus` | Hardware topology radar: USB/BT/NVMe interconnect map |
| `lukedaduke.power` | Battery status, charge graph, top consumers, power profiles |
| `lukedaduke.lidguard` | Timed lid-close stay-awake so agents and VMs keep running with the lid shut |
| `io.github.duketopceo.bumblebee` | Supply-chain exposure radar: packages and dev tools checked against a known-compromise catalog |
| `io.github.duketopceo.numbat` | AI-agent activity radar: live agent list and findings from Perplexity's numbat monitor |
| `io.github.duketopceo.pplx` | Quick-ask UI for the Perplexity Search API (`pplx` CLI, bring your own key) |
| `io.github.duketopceo.neo` | BrowserOS neo sidecar status and control: unit health, ports, MCP endpoint |
| `io.github.duketopceo.notch` | Mac-style notch island (panel): clock, weather, stocks, hover-expand tabs. **Self-contained** — works alone after install; optional Wisp / WordInk / Blip / herdr / snapdex / fan integrations detect-and-degrade |
| `io.github.duketopceo.wordink` | WordInk dictation: mic state icon, click to dictate, mic picker, recent dictations, weekly usage (local `wordink` CLI) |
| `io.github.duketopceo.hotkey-tally` | Counts how often each wrapped Hyprland binding is used (aggregate counts only, local) |

### Retired

`lukedaduke.connections`, `lukedaduke.ticker` and `lukedaduke.agents` are retired in favour of
Omarchy's built-in `omarchy.bluetooth` / `omarchy.network`, `mohamedmansour.finance`, and
`akitaonrails.ai-usagebar`. Their folders hold a final notice-only stub release.

## Deploy / visibility

This umbrella repo is **public**: https://github.com/duketopceo/omarchy-plugins

Each plugin is also published as its own installable repo (`manifest.json` at root, `omarchy plugin validate` clean):

| Plugin | Repo |
|---|---|
| `lukedaduke.fan` | https://github.com/duketopceo/omarchy-fan |
| `lukedaduke.standby` | https://github.com/duketopceo/omarchy-standby |
| `lukedaduke.copyq` | https://github.com/duketopceo/omarchy-copyq |
| `lukedaduke.nexus` | https://github.com/duketopceo/omarchy-nexus |
| `lukedaduke.power` | https://github.com/duketopceo/omarchy-power |
| `lukedaduke.lidguard` | https://github.com/duketopceo/omarchy-lidguard |
| `io.github.duketopceo.bumblebee` | https://github.com/duketopceo/omarchy-bumblebee |
| `io.github.duketopceo.numbat` | https://github.com/duketopceo/omarchy-numbat |
| `io.github.duketopceo.pplx` | https://github.com/duketopceo/omarchy-pplx |
| `io.github.duketopceo.neo` | https://github.com/duketopceo/omarchy-neo |
| `io.github.duketopceo.notch` | https://github.com/duketopceo/omarchy-notch (not yet published) |
| `io.github.duketopceo.wordink` | https://github.com/duketopceo/omarchy-wordink (not yet published) |
| `io.github.duketopceo.hotkey-tally` | https://github.com/duketopceo/omarchy-hotkey-tally (not yet published) |

Install any of them with:

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-fan
```

Until a mirror exists, install from this umbrella with `./scripts/install.sh --link` or `--copy` (covers notch and the other unpublished plugins).

To list on the marketplace, submit the per-plugin repo at [plugins.omarchy.org/publish](https://plugins.omarchy.org/publish.html).

This umbrella stays the authoring catalog — edit here, then `git subtree push --prefix=plugins/<id> <repo> main` to ship an update. Or install locally with `scripts/install.sh`.

See [docs/UPSTREAM.md](docs/UPSTREAM.md).

## Docs

- Plugin trust/reliability rules: [`docs/PLUGIN_CONTRACT.md`](docs/PLUGIN_CONTRACT.md)
- Active inventory review: [`docs/reviews/active-plugin-estate.md`](docs/reviews/active-plugin-estate.md)
- Deep runtime/source audit: [`docs/reviews/active-plugin-deep-audit.md`](docs/reviews/active-plugin-deep-audit.md)
- Host integration health: [`docs/HOST_INTEGRATION.md`](docs/HOST_INTEGRATION.md)
- Secret/data lifecycle: [`docs/DATA-LIFECYCLE.md`](docs/DATA-LIFECYCLE.md)
- Surface migration dry-run: [`docs/SURFACE-MIGRATION.md`](docs/SURFACE-MIGRATION.md)
- Release/publish workflow: [`docs/UPSTREAM.md`](docs/UPSTREAM.md)
- See `AGENTS.md` for agent context.
- Plan: `docs/plans/2026-09-02-001-feat-omarchy-plugins-marketplace-plan.md`
- New laptop restore: [`machine/INDEX.md`](machine/INDEX.md) and [`machine/RESTORE.md`](machine/RESTORE.md) (no secrets; private configs live in `duketopceo/dotfiles`)
