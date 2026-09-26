# AGENTS.md — Market Watchlist (`lukedaduke.ticker`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Bar widget for a fixed watchlist — gold, tech, nuclear, energy, rates. The bar
text shows a compact ticker; the dropdown is a `j`/`k`-navigable list where Enter
opens the selected symbol on TradingView. Quotes refresh every 60 s.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/lukedaduke.ticker/`. `scripts/publish.sh` runs `git subtree split` and
fast-forwards this repo's `main`. **A commit made directly here is deleted on the
next publish.** Make the change in the umbrella, then
`scripts/publish.sh ticker`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["bar-widget"]`, `barWidget.category: "Finance"` |
| `Panel.qml` | Bar text + dropdown. ~340 lines |
| `bin/market_stats.py` | Fetches quotes, emits bounded JSON. Stdlib only |
| `ROADMAP.md` | Planned work |
| `preview.png` | Marketplace listing image |

The panel execs the helper with the absolute interpreter `/usr/bin/python3`.

## Runtime Contract

- **No build step.** Nothing to compile. `manifest.json` must stay valid JSON.
- **QML cannot be checked outside Omarchy.** `Panel.qml` imports `Quickshell`,
  `Quickshell.Io`, `QtQuick.Layouts`, `qs.Commons`, and `qs.Ui`. The `qs.*`
  modules are provided by the host shell at runtime and are absent from a plain
  checkout, so `qmllint` will report unresolvable imports. Not a bug — do not
  rewrite the imports.
- `moduleName` and `ipcTarget` must both equal the manifest `id`
  (`lukedaduke.ticker`).
- **The last good snapshot must survive a failed fetch.** A network or API error
  keeps the previous quotes on screen rather than blanking the bar. Preserve this
  when touching the fetch or the error path.

## Validation

There is no test suite in this repo. From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/ -q          # includes tests/test_ticker_stats.py
```

Standalone:

```bash
python3 -m py_compile bin/*.py
```

The test suite requires Linux (it exercises GNU `head -z` and `/proc` paths used
elsewhere in the family), so on macOS expect unrelated failures from
`test_agents.py` / `test_fan_stats.py` while `test_ticker_stats.py` passes.

Real verification is on Linux with the plugin enabled: symbols appear in the bar,
the dropdown populates, and Enter opens TradingView.

## Runtime Requirements

- `python3` (the helper is stdlib-only; the panel execs `/usr/bin/python3`)
- `xdg-open` — opens the selected symbol on TradingView
- HTTPS reachability to `query1.finance.yahoo.com` (`/v8/finance/chart/`)

## Conventions

- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded palette hex.
- Keep the helper stdlib-only. Do not add a dependency; there is no lockfile or
  package manifest in this repo to carry one.
- Keep child `PATH` pinned to a fixed safe list and exec helpers by absolute
  path, so a `PATH`-preceding shadow binary cannot execute.
- Bound the helper's stdout — the QML side parses it.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.
