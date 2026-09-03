# omarchy-plugins

> First-party Omarchy bar plugins for Khan's laptop, packaged so they can later publish as `duketopceo/omarchy-plugins`.

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

## Deploy

Not published yet. Later:

```bash
gh repo create duketopceo/omarchy-plugins --source . --private --push
```

Omarchy's `omarchy plugin add <url>` expects **one plugin per git repo** (`manifest.json` at the repo root). Until we split remotes, use `scripts/install.sh`. Each `plugins/<id>/` directory is already a valid plugin root.

## Docs

- See `AGENTS.md` for agent context.
- Plan: `docs/plans/2026-09-02-001-feat-omarchy-plugins-marketplace-plan.md`
- New laptop restore: [`machine/INDEX.md`](machine/INDEX.md) and [`machine/RESTORE.md`](machine/RESTORE.md) (no secrets; private configs live in `duketopceo/dotfiles`)
