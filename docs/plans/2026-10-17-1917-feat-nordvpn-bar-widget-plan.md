---
date: 2026-10-17 19:17
title: "feat: NordVPN bar widget — binary on/off glyph + API-driven location picker"
type: feat
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# feat: NordVPN bar widget — binary on/off glyph + API-driven location picker

## Goal Capsule

**Objective:** Luke can turn NordVPN fully on (pick a location, connect) and fully off (one click, complete disconnect) from the Omarchy bar's center section, with the glyph always showing the true connection state.

**Means:** a `bar-widget` plugin `io.github.duketopceo.nordvpn` in this umbrella repo — a toggle-glyph that opens a location picker when off and disconnects when on, with picker data from NordVPN's public REST API and all state/control through the local `nordvpn` CLI daemon (KTD1, KTD2).

**Stop conditions:** do not edit `/usr/share/omarchy/`; do not commit or publish without explicit ask; no marketplace submission.

**Execution profile:** single agent, direct implementation. Finished when the verification contract passes and the widget behaves correctly live.

## Product Contract

### Summary

Ship a lightweight NordVPN bar widget. The glyph is a binary switch — nothing in between. Disconnected: click opens a picker of countries → cities → recommended servers (data from `api.nordvpn.com`); picking connects. Connected: click disconnects outright. A small status readout and a kill-switch row round out the panel.

### Problem Frame

NordVPN on this machine is CLI-only (`nordvpn-bin 5.4.1-1`; the `nordvpn-gui` binary doesn't exist on ARM64 — the app-menu entry was removed as dead). The daemon is running and the account is logged in (subscription to Mar 2027). No Omarchy plugin exists — first-party `omarchy.network` is Wi-Fi state only, and `omarchy.tailscale` is the closest shape but is ~2,300 lines. User's stated priority: "easy on, easy off — I hate the semi off and this and that."

### Requirements

- **R1** — The bar glyph shows exactly two connection states to the user: ON (connected) or OFF. Transitional CLI states (`connecting`) render as a busy glyph, never a third user-facing state.
- **R2** — Clicking the glyph while OFF opens the location picker; clicking while ON disconnects fully (`nordvpn disconnect`). No intermediate confirmation, no partial-off.
- **R3** — The picker lists countries and their cities plus recommended servers, sourced from NordVPN's public API (`api.nordvpn.com`), with `nordvpn countries` as the offline fallback.
- **R4** — Picking a location connects via `nordvpn connect <target>` (`<server>` short-name, `<country>`, or `<country> <city>` — the CLI's own grammar), then the panel closes and the glyph shows ON once `nordvpn status` reports connected.
- **R5** — The widget sits in the bar's center region (`defaultSection: "center"`), leftmost.
- **R6** — Connected-state detail (hostname, IP, uptime, protocol) and a kill-switch toggle row are the only extras in the panel. No autoconnect UI, no meshnet, no settings page.
- **R7** — Logged-out and daemon-down states degrade gracefully: glyph shows OFF, picker still opens, an inline hint tells the user to `nordvpn login` or start `nordvpnd` instead of failing silently.

### Key Decisions

- **Binary toggle-glyph over always-open panel** — `session-settled:` user picked "easy on, easy off" semantics; the glyph itself is the switch, not a dropdown with buttons. Governs R1, R2.
- **Public API for discovery, CLI for control** — `session-settled:` "build it over their api so we can do our own." The API gives cities+load that `nordvpn countries` cannot. Only the daemon can tunnel, so control stays CLI. Governs R3, R4.
- **NordVPN look via glyph/wordmark, colors stay theme tokens** — repo AGENTS.md forbids hardcoded hex; brand feel comes from the shield glyph + "NORDVPN" label, tinted with `Color.accent`. Governs R6.

### Scope Boundaries

**In:** binary on/off, country/city/server picker, connected detail, killswitch toggle, graceful degraded states.

**Out (non-goals, considered and not built):** autoconnect UI, meshnet, threat-protection toggles, server pinning/favorites, tray icon — each adds states or persistence the user explicitly doesn't want; revisit only if asked. Marketplace submission — separate request when desired.

## Planning Contract

### Key Technical Decisions

- **KTD1 — Toggle-glyph interaction model.** `BarIconButton.onPressed`: `connected ? control("disconnect") : toggle()` (open picker). A Disconnect button inside the panel is redundant-but-cheap backup. `connecting` state from `nordvpn status` shows a busy glyph that still accepts the click (disconnects — that's the "easy off" escape hatch).
- **KTD2 — Hybrid data path.** `bin/probe_nordvpn.py` gains API verbs using stdlib `urllib.request` (8s timeout): `countries` → `/v1/servers/countries` (150 entries with cities, fallback to `nordvpn countries`), `servers <country_id>` → `/v1/servers/recommendations?filters[country_id]=N&limit=8` (hostname, name, load). Control/state stays on `/usr/bin/nordvpn` — status, connect (server short-name = hostname minus `.nordvpn.com`, or `<country> <city>`), disconnect, `set killswitch on|off`.
- **KTD3 — Fetch on open, not on poll.** Status polls every ~20s hit the CLI only. API picker data loads once per panel-open and is cached for the panel's lifetime — a 20s poll hammering api.nordvpn.com is the wrong cost profile.
- **KTD4 — Brand without hardcoded hex.** Shield glyph (nerd-font VPN/shield char) + "NORDVPN" wordmark; accent/dim/urgent from `qs.Commons` `Color` — same as every plugin in this repo.

### High-Level Technical Design

```text
BarIconButton (center section)
  │ click
  ├─ connected ──► probe disconnect ──► glyph OFF
  └─ off ──► panel opens
       ├─ statusProc (CLI, ~20s poll)  → state, hostname, ip, uptime, killswitch
       └─ apiProc (api.nordvpn.com, on open)
            → countries + cities  ──► picker list
            → pick city/server    ──► probe connect <target> ──► close ──► glyph ON
```

### Assumptions

- `nordvpn connect <server>` accepts the API hostname short-name (`jp35`-style; documented in `nordvpn connect --help`). Two-arg `<country> <city>` is the city fallback when the API is unreachable.
- Logged-in + daemon-up is the normal state (verified); R7 paths are for regression only.
- `moduleName`/`ipcTarget` must equal the manifest `id` (repo runtime contract).

## Output Structure

```
plugins/io.github.duketopceo.nordvpn/
  manifest.json            # exists — needs defaultSection: "center"
  Panel.qml                # to write — toggle-glyph + picker panel
  bin/
    probe_nordvpn.py       # exists — extend with API verbs
  README.md                # new — install/remove/deps
```

## Implementation Units

### U1. Probe helper: API picker verbs + connect targets

**Goal:** `probe_nordvpn.py` serves country/city/server picker data from the NordVPN public API with CLI fallback, and accepts connect targets by server short-name, country, or country+city.

**Requirements:** R3, R4, R7 · **Dependencies:** none

**Files:**
- `plugins/io.github.duketopceo.nordvpn/bin/probe_nordvpn.py`

**Approach:**
1. Add `countries` verb: GET `api.nordvpn.com/v1/servers/countries` → emit `[{id, name, code, cities:[{name, dns_name}], serverCount}]` sorted by name. On any failure (timeout, non-200, parse) fall back to `nordvpn countries` flat list with `cities: []`.
2. Add `servers <country_id>` verb: GET `…/recommendations?filters[country_id]=N&limit=8` → emit `[{hostname, name, load}]`.
3. Extend `connect`: accept `connect <server>` (short-name matching `^[a-z]{2}\d+$`), `connect <country>` (validated against countries list as today), and `connect <country> <city>` (city validated against the API city list; two-argv form the CLI supports).
4. Keep the existing bounded-subprocess/JSON-emit conventions; add one `urllib.request` fetcher with 8s timeout + a shared `_api_get` that returns parsed JSON or raises for fallback handling.

**Patterns to follow:** the existing `_run`/`_emit`/`_kv` helpers already in the file; `probe_neo.py`'s verb dispatch and bounded-output contract.

**Test scenarios:**
- `status` returns state/logged_in/killswitch/countries (verified: disconnected, logged in, 150 countries).
- `countries` emits a non-empty array with `cities` populated for a multi-city country (e.g., United States).
- `servers 2` emits ≤8 entries each with `hostname` matching `\w+\.nordvpn\.com` and numeric `load`.
- `countries` with API unreachable (simulate via `HTTPS_PROXY=http://127.0.0.1:1`) still emits the CLI country list — picker never goes empty.
- `connect bogus!` rejects with an `error` field, never reaches the CLI.
- `connect United_States Phoenix` is accepted only when Phoenix is a real API city for that country.

**Verification:** `python3 -m py_compile` clean; each verb prints exactly one JSON object; fallback path exercised.

### U2. Panel.qml: toggle-glyph + location picker

**Goal:** the bar glyph is the on/off switch — disconnected opens the picker, connected disconnects — with a picker driven by U1's API verbs and a compact connected-detail + killswitch block.

**Requirements:** R1, R2, R4, R5, R6, R7 · **Dependencies:** U1

**Files:**
- `plugins/io.github.duketopceo.nordvpn/Panel.qml`

**Approach:**
1. `BarIconButton` shield glyph; `onPressed` branches on `root.connected` (KTD1). Tint: accent when connected, dim when off; `connecting` shows the busy tint but stays clickable.
2. `KeyboardPanel` opens only in the OFF direction: header (glyph + "NORDVPN" + status pill), then the picker — `QUICK` row ("Recommended" → `connect` no-arg) + scrollable country rows; expanding a country lazily runs `servers <id>` and shows city/server rows with load %.
3. Connected-detail block (hostname · IP · uptime · protocol) and a kill-switch toggle row sit below the picker per R6.
4. OFF/edge states (R7): `!logged_in` or `!cli` renders the hint line instead of the picker.
5. `statusTimer` polls `status` every 20s (CLI only, KTD3); `apiProc` runs on `onOpenedChanged`; `ctrlProc` handles connect/disconnect/killswitch with the group-kill deadline pattern from neo.

**Patterns to follow:** `plugins/io.github.duketopceo.neo/Panel.qml` — procEnv, `groupKill`, `statusDeadline`/`ctrlDeadline` timers, `PanelSectionHeader`, pill/button styling. Keep it ~450-550 lines; no Tailscale-scale features.

**Test expectation:** none — QML panel; verified live per Verification Contract.

### U3. Manifest center-section fix + README + validation

**Goal:** manifest declares `defaultSection: "center"`; a README documents install/remove and the `nordvpn-bin` dependency; repo validation passes.

**Requirements:** R5 · **Dependencies:** U2

**Files:**
- `plugins/io.github.duketopceo.nordvpn/manifest.json`
- `plugins/io.github.duketopceo.nordvpn/README.md`

**Approach:** change `defaultSection` to `"center"`; README covers `omarchy plugin add` path (subtree-publish caveat per repo model), the `nordvpn-bin` + `nordvpnd.service` + `nordvpn` group prerequisites, and the offline-fallback behavior. Run the validation suite.

**Test expectation:** none — config/docs; validation commands are the check.

**Verification:** `python3 scripts/validate-manifests.py`, `python3 -m pytest tests/ -q`, `omarchy plugin validate plugins/io.github.duketopceo.nordvpn` all pass.

## Verification Contract

- `python3 scripts/validate-manifests.py` — clean
- `python3 -m pytest tests/ -q` — clean (add `tests/test_nordvpn.py` only if the repo's existing test pattern covers probe helpers; check `tests/test_neo.py` shape first)
- `omarchy plugin validate plugins/io.github.duketopceo.nordvpn` — clean
- `python3 -m py_compile plugins/io.github.duketopceo.nordvpn/bin/*.py` — clean
- **Live smoke** (after `install.sh --link` or `--copy`): glyph sits center-left; OFF-click opens picker with populated countries; pick a location → connects (confirm `nordvpn status`); ON-click → disconnected (confirm); killswitch row toggles `nordvpn settings`.

## Definition of Done

- All verification-contract items pass, including live smoke on the real bar.
- Glyph never presents a third state; OFF→pick→ON and ON→OFF are one click each (plus the pick).
- Picker populated from the API in the normal case, CLI fallback when offline.
- No leftover scaffolding: no dead verbs, no unused props, no committed secrets; `version` 0.1.0 in the manifest.
