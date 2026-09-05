# omarchy-plugins

> Luke's personal Omarchy bar plugins plus a laptop restore index. Not first-party Omarchy, and not a marketplace listing.

## Stack

- Quickshell / QML (Omarchy shell plugins)
- Python 3 helpers (fan stats, market quotes)
- Bash installer

## Local Setup

```bash
git clone https://github.com/duketopceo/omarchy-plugins
cd omarchy-plugins

uv run --with pytest pytest -q
python scripts/validate-manifests.py

# live install (hot-reload from this tree)
./scripts/install.sh --link
```

No `.env` required. See `.env.example`.

## Plugins

| Id | What |
|---|---|
| `lukedaduke.fan` | RAM, CPU/GPU/NVMe temps, top processes, fan presets + custom curves |
| `lukedaduke.ticker` | Watchlist quotes with TradingView jump |
| `lukedaduke.agents` | Fork of `omarchy.agents` with extra providers |
| `lukedaduke.standby` | OLED nightstand overlay: clock, weather, markets, red tint, caffeine |

## Deploy / visibility

This umbrella repo is **public**: https://github.com/duketopceo/omarchy-plugins

Each plugin is also published as its own installable repo (`manifest.json` at root, `omarchy plugin validate` clean):

| Plugin | Repo |
|---|---|
| `lukedaduke.fan` | https://github.com/duketopceo/omarchy-fan |
| `lukedaduke.ticker` | https://github.com/duketopceo/omarchy-ticker |
| `lukedaduke.agents` | https://github.com/duketopceo/omarchy-agents |
| `lukedaduke.standby` | https://github.com/duketopceo/omarchy-standby |

Install any of them with:

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-fan
```

To list on the marketplace, submit the per-plugin repo at [plugins.omarchy.org/publish](https://plugins.omarchy.org/publish.html).

This umbrella stays the authoring catalog — edit here, then `git subtree push --prefix=plugins/<id> <repo> main` to ship an update. Or install locally with `scripts/install.sh`.

See [docs/UPSTREAM.md](docs/UPSTREAM.md).

## Docs

- See `AGENTS.md` for agent context.
- Plan: `docs/plans/2026-09-02-001-feat-omarchy-plugins-marketplace-plan.md`
- New laptop restore: [`machine/INDEX.md`](machine/INDEX.md) and [`machine/RESTORE.md`](machine/RESTORE.md) (no secrets; private configs live in `duketopceo/dotfiles`)
