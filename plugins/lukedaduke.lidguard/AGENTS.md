# AGENTS.md — Lid Guard (`lukedaduke.lidguard`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Timed lid-close stay-awake in the Omarchy bar. Arms a
`handle-lid-switch` block inhibitor for 1h/2h/4h/8h/∞ so the machine
keeps running (agents, VMs, builds) with the lid shut, then releases it
automatically. Distinct from `omarchy toggle idle` — that gates the idle
daemon; this gates the hardware lid event in logind.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/lukedaduke.lidguard/`. `scripts/publish.sh` runs `git subtree split`
and fast-forwards this repo's `main`. **A commit made directly here is deleted
on the next publish.** Make the change in the umbrella, then
`scripts/publish.sh lukedaduke.lidguard`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["bar-widget"]`, `barWidget.category: "System"` |
| `Panel.qml` | Bar glyph + duration-picker dropdown |
| `bin/lidguard.py` | `status` / `arm <seconds\|inf>` / `disarm` → one JSON object |

## Runtime Contract

- `moduleName` and `ipcTarget` must both equal the manifest `id`
  (`lukedaduke.lidguard`).
- **No build step.** `manifest.json` stays valid JSON; helper is stdlib-only.
- Mechanism: `systemd-run --user --replace --unit=lidguard` wrapping
  `systemd-inhibit --what=handle-lid-switch ... sleep <N>`. The inhibitor is
  a **block** lock on the logind lid event — it survives lid close because
  the user session does.
- Expiry is a state file (`~/.local/state/lidguard/expires`, epoch or `inf`),
  not a systemd timer property — keep `status` honest when the unit was
  armed outside the helper by reporting `remaining_s: null`.
- `systemctl --user` needs the user bus — the helper reconstructs
  `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` because the panel scrubs env.
- The glyph must be a codepoint present in the bar font (JetBrainsMono NF);
  currently `󰐥` (U+F0425). Verify with `fc-list ":charset=<hex>"`.
- Two-state glyph: `accent` armed / `dim` disarmed — no third state.
- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded hex.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.

## Validation

From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m py_compile plugins/lukedaduke.lidguard/bin/lidguard.py
python3 plugins/lukedaduke.lidguard/bin/lidguard.py status   # → JSON
omarchy plugin validate plugins/lukedaduke.lidguard
```

Real verification on the live bar: arm 1h → `systemd-inhibit --list` shows
the `handle-lid-switch` block lock → `systemctl --user stop lidguard` (or
panel disarm) releases it.

## Runtime Requirements

- `python3`, `systemd` user manager, `systemd-inhibit`
- logind honoring `handle-lid-switch` block inhibitors (standard)
