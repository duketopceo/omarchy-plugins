# AGENTS.md — Standby (`lukedaduke.standby`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

An OLED-friendly nightstand overlay for Omarchy: an iPhone-StandBy-style
horizontal display that can be summoned manually without touching the screensaver
or lock screen. Shows the time, date, and weather.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/lukedaduke.standby/`. `scripts/publish.sh` runs `git subtree split` and
fast-forwards this repo's `main`. **A commit made directly here is deleted on the
next publish.** Make the change in the umbrella, then
`scripts/publish.sh standby`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["overlay"]`, `entryPoints.overlay` |
| `Standby.qml` | The entire overlay. Single QML file |
| `bin/standby-data` | Fetches weather + locality, emits JSON. Python despite the extensionless name |
| `ROADMAP.md` | Planned work |
| `preview.png` | Marketplace listing image |

## Runtime Contract

- **This is the only `overlay` in the family.** Every other plugin is a
  `bar-widget` (or a `service`). The difference matters: an overlay is a
  full-screen layer, not a bar item, and it uses `Quickshell.Wayland` for
  layer-shell surface behavior.
- **`moduleName` / `ipcTarget` do not apply here.** Overlays do not set them, and
  the manifest `id` (`lukedaduke.standby`) is the only identity. Do not add
  `moduleName` to `Standby.qml` to satisfy a rule you saw in a sibling plugin —
  the `bar-widget` invariant does not extend to overlays.
- `bin/standby-data` is **Python with no `.py` extension** and a
  `#!/usr/bin/python3` shebang. The panel invokes it with that absolute
  interpreter. Do not rename it to `standby-data.py` without updating the
  invocation — the extensionless name is deliberate and matches how the QML
  calls it.
- **No build step.** Nothing to compile. `manifest.json` must stay valid JSON.
- **QML cannot be checked outside Omarchy.** `Standby.qml` imports `Quickshell`,
  `Quickshell.Io`, `Quickshell.Wayland`, and `qs.Commons`. The `qs.*` module comes
  from the host shell at runtime, so `qmllint` reports unresolvable imports in a
  plain checkout. Not a bug.
- OLED burn-in is a design constraint, not a preference: keep static pixels dim
  and the layout from parking bright UI in one corner for long stretches.

## Validation

No test suite in this repo, but the umbrella covers the helper well in
`tests/test_standby.py` (~30 tests). It **imports the extensionless
`bin/standby-data` as a module** and neutralizes the `SIGALRM` deadline `main()`
arms. From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/test_standby.py -q
```

Coverage concentrates on hostile input to the location lookup — invalid JSON, a
JSON array body with no `.get`, non-numeric or dict/list lat/lon, and absurdly
large coordinates that would raise `OverflowError` out of `float()`. Those are
real regressions that were fixed once; keep them covered. `iso_to_hm` formatting
is tested too.

These tests are platform-independent and pass on macOS.

**They cover the helper, not the overlay.** `Standby.qml` has no automated
coverage. Real verification is manual: on Linux with the plugin enabled, summon
the overlay, confirm the clock renders, and confirm weather appears or degrades
to a placeholder when the network is down. Say so explicitly in any PR.

## Runtime Requirements

- `python3` at `/usr/bin/python3`
- Network access to `api.open-meteo.com` (weather forecast) and `ipapi.co`
  (locality lookup) over HTTPS
- Wayland compositor with layer-shell support (Omarchy provides this)

## Conventions

- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded palette hex.
- Keep the helper stdlib-only; no package manifest exists here to carry a
  dependency.
- Keep child `PATH` pinned to a fixed safe list and exec the helper by absolute
  path, so a `PATH`-preceding shadow binary cannot execute.
- Bound the helper's stdout — the QML side parses it.
- A failed fetch must leave the clock working and degrade the weather block, not
  blank the overlay. It is a clock first.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.
