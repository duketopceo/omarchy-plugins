# AGENTS.md — NordVPN (`io.github.duketopceo.nordvpn`)

> This file is the agent entry point for this repo.
> Full agent context lives at: https://github.com/duketopceo/luke-agents

Inherits from [luke-agents/AGENTS.md](https://github.com/duketopceo/luke-agents/blob/main/AGENTS.md). This file specializes; it does not replace.

## What This Repo Does

Binary on/off NordVPN control in the Omarchy bar (center section). The glyph
IS the switch: OFF → click opens a location picker (recommended + five US
cities); picking runs `nordvpn connect`. ON → click runs `nordvpn
disconnect`. A connected-detail block (hostname/IP/uptime/protocol/transfer)
and a kill-switch toggle are the only extras — no semi-states.

## Provenance — edit in the umbrella, not here

This repo is the published subtree of
[`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) at
`plugins/io.github.duketopceo.nordvpn/`. `scripts/publish.sh` runs `git subtree split`
and fast-forwards this repo's `main`. **A commit made directly here is deleted on
the next publish.** Make the change in the umbrella, then `scripts/publish.sh io.github.duketopceo.nordvpn`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract. `kinds: ["bar-widget"]`, `defaultSection: "center"` |
| `Panel.qml` | Toggle-glyph + picker dropdown |
| `bin/probe_nordvpn.py` | Status + control probe, one JSON object on stdout |

## Runtime Contract

- `moduleName` and `ipcTarget` must both equal the manifest `id`
  (`io.github.duketopceo.nordvpn`).
- **No build step.** `manifest.json` stays valid JSON; helper is stdlib-only.
- The Panel root MUST set `implicitWidth`/`implicitHeight` from the button —
  a widget without them renders at zero width (invisible) with no error.
- The glyph must be a codepoint present in the bar font (JetBrainsMono NF);
  `fc-list ":charset=<hex>"` to check. Currently `󰦝` (U+F099D).
- Two-state glyph: `foreground: connected ? accent : dim` — never render a
  third user-facing state; `connecting` may light the glyph but stays clickable.
- `nordvpn` needs `HOME` in its env — a scrubbed subprocess env fatals with
  "cannot get user home dir". The helper reconstructs HOME/XDG_RUNTIME_DIR.
- Connect grammar is the CLI's own: `connect [server-short-name]` (e.g.
  `us12980`), `connect <Country_Name>`, `connect <Country_Name> <City>`.
- API verbs (`countries`, `servers`) hit `api.nordvpn.com` unauthenticated;
  they exist for richer pickers but the panel currently uses a static list —
  keep them working anyway, and keep the CLI fallback in `countries`.
- Theme with `qs.Commons` `Color` / `Style` only. No hardcoded hex.
- Never edit `/usr/share/omarchy/`.
- Bump `version` in `manifest.json` when shipping a behavior change.

## Validation

From the umbrella:

```bash
python3 scripts/validate-manifests.py
python3 -m pytest tests/ -q          # includes tests/test_nordvpn.py
python3 -m py_compile plugins/io.github.duketopceo.nordvpn/bin/*.py
omarchy plugin validate plugins/io.github.duketopceo.nordvpn
```

Real verification is on the live bar: glyph dim when disconnected, accent
when connected, click-through connect/disconnect round-trip.

## Runtime Requirements

- `nordvpn-bin` (CLI + `nordvpnd.service`), user in `nordvpn` group, logged in
- `python3` at `/usr/bin/python3`
- HTTPS egress to `api.nordvpn.com` only if API verbs are used
