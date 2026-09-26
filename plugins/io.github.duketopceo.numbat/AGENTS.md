# AGENTS.md — Numbat (`io.github.duketopceo.numbat`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

AI-agent activity radar for the Omarchy bar. Ambient visibility into what the
coding agents on this machine (Devin, Cursor, Claude Code, and others) are
actually doing: a live agent list, a 24h findings count, and a findings feed.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/io.github.duketopceo.numbat/`. `scripts/publish.sh` runs `git subtree split`
and fast-forwards this repo's `main`. **A commit made directly here is deleted on the
next publish.** Make the change in the umbrella, then `scripts/publish.sh numbat`.

The id is `io.github.duketopceo.*`, not `lukedaduke.*` like the rest of the family.
That is intentional and matches upstream. The manifest `id`, the folder name, and
`moduleName` must all agree.

## Upstream

Tracks [`perplexityai/numbat`](https://github.com/perplexityai/numbat).
`UPSTREAM.md` records the sync model. Read it before porting an upstream change.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. **`kinds: ["service", "bar-widget"]`** |
| `Service.qml` | Always-on service. Tails the record stream and raises toasts |
| `Panel.qml` | Bar radar glyph + dropdown (findings feed, per-agent last activity) |
| `LocalSettings.qml` | User-tunable settings bound into the UI |
| `bin/probe_numbat.py` | Reads numbat's record files, emits bounded JSON |
| `UPSTREAM.md` | Upstream sync model |
| `preview.png` | Marketplace listing image |

## Runtime Contract

- **This is a `service` + `bar-widget` plugin.** The `service` is kept loaded by
  the shell and is what tails `~/.numbat/records.ndjson` and fires findings
  toasts. Do not move that work into the panel — the panel lives and dies with
  the UI, the service does not.
- The live event stream is `~/.numbat/records.ndjson`, produced by numbat's
  `--emit all` hooks. The panel renders it; it does not produce it.
- The bar glyph tints urgent when findings landed in the last 24h. That is a
  rolling window over the record file, not a stored flag.
- `moduleName` and `ipcTarget` must both equal the manifest `id`
  (`io.github.duketopceo.numbat`).
- **No build step.** Nothing to compile. `manifest.json` must stay valid JSON.
- **QML cannot be checked outside Omarchy.** The QML imports `Quickshell`,
  `Quickshell.Io`, `Quickshell.Wayland`, `QtQuick.Layouts`, `QtQml.Models`,
  `qs.Commons`, and `qs.Ui`. The `qs.*` modules come from the host shell at
  runtime, so `qmllint` reports unresolvable imports in a plain checkout. Not a
  bug.

## Validation

There is no test suite in this repo. From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/ -q          # includes tests/test_numbat.py
```

Standalone:

```bash
python3 -m py_compile bin/*.py
```

The umbrella suite requires Linux (GNU `head -z`, `/proc/meminfo`), so on macOS
expect unrelated failures from `test_agents.py` / `test_fan_stats.py` while
`test_numbat.py` passes.

Real verification is on Linux with the plugin enabled and numbat emitting records:
the glyph reflects agent state, a finding produces a toast, and the feed lists
rule, agent, and relative time. State in any PR whether you had a live record
stream or only exercised the empty state.

## Runtime Requirements

- `python3` (the panel and service exec `/usr/bin/python3`)
- A readable `~/.numbat/records.ndjson` for anything to display
- Optional: `btop` + `omarchy-launch-or-focus-tui` for the middle-click launcher

## Conventions

- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded palette hex.
- Keep the helper stdlib-only; no package manifest exists here to carry a
  dependency.
- Keep child `PATH` pinned to a fixed safe list and exec helpers by absolute
  path, so a `PATH`-preceding shadow binary cannot execute.
- Bound the helper's stdout — the QML side parses it.
- The record file can contain content from other tools. Treat it as untrusted
  input: bound sizes, skip malformed lines, and never evaluate it.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.
