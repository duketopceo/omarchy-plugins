# AGENTS.md — Neo (`io.github.duketopceo.neo`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

**Local-only** bar status + control widget for the BrowserOS neo sidecar:
`browserclaw-{chromium,shim,server}` systemd user units behind MCP at
`http://127.0.0.1:9211/mcp`. Glyph shows health; the dropdown shows unit
state, port bindings, the MCP endpoint, and Start/Restart/Stop controls.
When the units are not installed the glyph hides and polling stops.

## Provenance — edit in the umbrella only

This plugin lives only under
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/io.github.duketopceo.neo/`. It is **excluded from** `scripts/publish.sh`
(`catalog.json` marks `localOnly: true`). There is no subtree publish target.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["bar-widget"]` |
| `Panel.qml` | Bar glyph + dropdown (units, ports, endpoint, controls) |
| `bin/probe_neo.py` | Status probe + bounded unit control, one JSON object on stdout |

## Runtime Contract

- `moduleName` and `ipcTarget` must both equal the manifest `id`
  (`io.github.duketopceo.neo`).
- **No build step.** `manifest.json` stays valid JSON; helpers stay
  stdlib-only.
- **Machine-shaped by design**: unit names/ports/endpoint are hardcoded to
  the local sidecar layout. If the deployment changes, change
  `bin/probe_neo.py` constants — don't add config plumbing.
- The helper execs binaries by absolute path under a fixed `PATH`;
  `XDG_RUNTIME_DIR` is reconstructed from the uid because `systemctl --user`
  needs the caller's user bus and the panel env is scrubbed.
- Control verbs can legitimately wait out a unit's `TimeoutStopSec` — the
  helper's JOB_DEADLINE_S (50s) and the panel's control deadline (55s) are
  sized for that; do not shrink them below a stop timeout.
- Status payloads include `capabilities.sidecar`. False only when `systemctl
  show` exits 0 and every unit reports `LoadState=not-found`. Nonzero rc,
  timeout, masked/error/missing LoadState must not hide the widget.
- MCP "up" means a real `initialize` answered `serverInfo` — keep that the
  truth test; a bound socket alone can be a wedged process.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.

## Validation

From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/ -q          # includes tests/test_neo.py
python3 -m py_compile plugins/io.github.duketopceo.neo/bin/*.py
```

Real verification is on Linux with the sidecar installed: the pill reads
RUNNING when `browserclaw-*` units are active and MCP answers; Restart cycles
the stack and the glyph recovers.
