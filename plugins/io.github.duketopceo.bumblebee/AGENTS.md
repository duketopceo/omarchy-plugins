# AGENTS.md — Bumblebee (`io.github.duketopceo.bumblebee`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Supply-chain exposure radar for the Omarchy bar. Periodically scans installed
packages, lockfiles, extension manifests, and MCP configs against a catalog of
known-compromised components, and surfaces the count before you find out the hard
way. The bar shield turns urgent and the dropdown lists each exposure.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/io.github.duketopceo.bumblebee/`. `scripts/publish.sh` runs
`git subtree split` and fast-forwards this repo's `main`. **A commit made directly
here is deleted on the next publish.** Make the change in the umbrella, then
`scripts/publish.sh bumblebee`.

The id is `io.github.duketopceo.*`, not `lukedaduke.*` like the rest of the family.
That is intentional and matches upstream. The manifest `id`, the folder name, and
`moduleName` must all agree.

## Upstream

Tracks [`perplexityai/bumblebee`](https://github.com/perplexityai/bumblebee).
`UPSTREAM.md` records the sync model. Read it before porting an upstream change.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. **`kinds: ["service", "bar-widget"]`** |
| `Service.qml` | Always-on service. Keeps scans and toasts running in the background |
| `Panel.qml` | Bar shield + dropdown of exposures |
| `LocalSettings.qml` | User-tunable settings bound into the UI |
| `bin/scan_bumblebee.py` | Scans the machine, emits bounded JSON |
| `bin/refresh_catalog.py` | Refreshes the known-compromised catalog |
| `catalog/exposures.json` | The catalog data |
| `UPSTREAM.md` | Upstream sync model |
| `preview.png` | Marketplace listing image |

## Runtime Contract

- **This is a `service` + `bar-widget` plugin.** The `service` component is kept
  loaded by the shell and runs scans on a stale-cache refresh; the bar widget only
  renders. Do not move scan work into the panel — the panel is created and
  destroyed with the UI, the service is not.
- Scans are rate-limited: the helper re-scans at most on a stale cache, not on
  every panel open. Preserve that bound.
- **New-exposure detection is baseline-relative.** A scan only escalates when it
  finds exposures absent from the previous baseline. Resetting or clearing the
  baseline silently suppresses alerts — treat the baseline as security state.
- `moduleName` and `ipcTarget` must both equal the manifest `id`
  (`io.github.duketopceo.bumblebee`).
- **No build step.** Nothing to compile. `manifest.json` must stay valid JSON.
- **QML cannot be checked outside Omarchy.** The QML imports `Quickshell`,
  `Quickshell.Io`, `Quickshell.Wayland`, `qs.Commons`, and `qs.Ui`. The `qs.*`
  modules come from the host shell at runtime, so `qmllint` reports unresolvable
  imports in a plain checkout. Not a bug.

## Validation

There is no test suite in this repo. From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/ -q          # includes tests/test_bumblebee.py
```

Standalone:

```bash
python3 -m py_compile bin/*.py
```

The umbrella suite requires Linux (GNU `head -z`, `/proc/meminfo`), so on macOS
expect unrelated failures from `test_agents.py` / `test_fan_stats.py` while
`test_bumblebee.py` passes.

Real verification is on Linux with the plugin enabled: the shield renders, a scan
completes, and adding a known-bad entry to `catalog/exposures.json` produces an
urgent state. State in any PR whether you exercised a real scan or only the UI.

## Runtime Requirements

- `python3` (the panel and service exec `/usr/bin/python3`)
- Readable package-manager state, lockfiles, extension manifests, and MCP configs
  for the scan to have anything to read
- HTTPS egress to GitHub for `refresh_catalog.py`

## Conventions

- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded palette hex.
- Keep the helpers stdlib-only; no package manifest exists here to carry a
  dependency.
- Keep child `PATH` pinned to a fixed safe list and exec helpers by absolute
  path, so a `PATH`-preceding shadow binary cannot execute.
- Bound the helpers' stdout — the QML side parses them.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.
