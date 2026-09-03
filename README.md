# omarchy-plugins

> Private working catalog of first-party Omarchy bar plugins plus a laptop restore index. Not the public marketplace listing.

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
| `lukedaduke.fan` | RAM, CPU/GPU/NVMe temps, top processes, fan presets |
| `lukedaduke.ticker` | Watchlist quotes with TradingView jump |
| `lukedaduke.agents` | Fork of `omarchy.agents` with extra providers |

## Deploy / visibility

This GitHub repo is **private**. Clone with SSH after `gh auth`.

Omarchy's `omarchy plugin add <url>` and the [official marketplace](https://plugins.omarchy.org/publish.html) both require a **public** git repo with `manifest.json` at the **root**. This umbrella cannot be submitted as-is.

When a plugin is ready to list:

1. Split that directory into its own public repo (`duketopceo/omarchy-fan`, etc.).
2. `omarchy plugin validate` on it.
3. Submit at [plugins.omarchy.org/publish](https://plugins.omarchy.org/publish.html) (or PR a catalog entry if a listing uses `plugins.txt`).

Until then, install with `scripts/install.sh`. Each `plugins/<id>/` is already a valid plugin root.

See [docs/UPSTREAM.md](docs/UPSTREAM.md).

## Docs

- See `AGENTS.md` for agent context.
- Plan: `docs/plans/2026-09-02-001-feat-omarchy-plugins-marketplace-plan.md`
- New laptop restore: [`machine/INDEX.md`](machine/INDEX.md) and [`machine/RESTORE.md`](machine/RESTORE.md) (no secrets; private configs live in `duketopceo/dotfiles`)
