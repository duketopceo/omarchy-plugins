---
title: Island Pages - Plan
type: feat
date: 2026-11-16
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
origin: docs/plans/2026-11-14-feat-island-plan.md
execution: code
---

# Island Pages - Plan

## Goal Capsule

- **Objective:** The Island's expanded card becomes a small set of pages: Home opens by default and answers "what is happening now", Music holds the Now Playing view, Agents shows coding sessions that need Luke first, System shows machine state, and More holds the rest (Shots, Messages, Dayflow, Settings), with a More page promoted into the chip row while it has something live.
- **Means:** A pure `Pages.js` page registry (detection, promotion, page ids), one generalized committed-height rule in `Presentation.js`, two read-only Python helpers (`bin/island-status`, `bin/island-agents`) that normalize machine state into JSON, small pure ES5 modules for each page's formatting, and one QML page component per page inside `Card.qml`.
- **Authority:** P1 KTD2 (hot-zone and mask commit rules) wins on sizing mechanics. The owner's session decisions below supersede P1 R16's five-chip cap (six chips at most while one page is promoted). This plan's KTDs win on page structure and sources.
- **Stop conditions:** Stop if a page would need the card height or hot zone to change while the card is open (P1 KTD2). Stop if any source can only be read by writing to it or by a new network call that Omarchy does not already make. Stop if something visible today (time, date, DND bell, privacy dots, live activities, alerts) would no longer be shown.
- **Execution profile:** Quickshell QML plus ES5 modules tested with node through pytest; Python helpers tested with pytest fixtures (`--root` style). Live checks via IPC and screenshots only; no pointer movement.
- **Who finishes:** One PR, `feat/island-pages`, off `main` (27a1042); version 0.4.0.

## Product Contract

### Summary

Restructure the expanded card from two pages (Now, Settings) into Home, Music, Agents, System and More, with More's entries (Shots, Messages, Dayflow, Settings) reachable from a list and promoted into the chip row while live.

### Problem Frame

The card's Now page mixes the clock, one large activity block and two rows; everything else the owner wants at a glance (weather, battery, Tailscale, agents waiting on input, machine load) lives in separate bar widgets or nowhere. The P1 clutter budget forbade a tab dashboard; the owner chose a bounded page set instead.

### Requirements

- R1. Chip row: Home, Music, Agents, System, More, in that order, each shown only when its backend is detected (Home, System and More always). At most 6 chips.
- R2. Shots, Messages and Dayflow are listed on the More page. While one has something live (unseen screenshot, unread message, Dayflow recording or paused) it is promoted into the chip row just before More. Promotion order is Messages, Shots, Dayflow, and promotions stop at 6 chips. Settings lives under More and is never promoted.
- R3. Home opens by default and shows: time and date; weather now (when Omarchy's weather is in the bar and the weather setting is on); DND bell and privacy dots as today; status dots (battery %, Tailscale up/down, VPN on); the next calendar event with Join and countdown; a compact strip of live activities (timer, recording, dictation, charging, media, Bluetooth) with each one's primary control; quick toggles for Do Not Disturb (Omarchy's toggle) and mic mute (`wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle`).
- R4. Music shows the Now Playing view from #78 unchanged except fitting the page frame. The Music chip exists while a player has a track. The Home strip's media row opens Music.
- R5. Agents lists herdr sessions (from `herdr-app ls`) and live Claude Code sessions (from `~/.claude/sessions/*.json` whose pid is alive), sessions needing input first. Each row's action focuses its terminal window through Hyprland (`hl.dsp.focus`); herdr rows also ask herdr to focus the terminal. Approve/deny is out of scope.
- R6. System shows battery % and state, power profile (when `powerprofilesctl` answers), fan mode (when the lukedaduke.fan helper's state exists) with a button that opens the fan panel through `omarchy-shell shell toggle lukedaduke.fan`, CPU and memory use, network (interface and SSID) and Tailscale status. CPU, memory, network and Tailscale are sampled only while the System page is visible.
- R7. Each page is content-sized: the card height is computed when the card opens or the page changes and never changes while open (P1 KTD2).
- R8. Nothing visible today disappears: time, date, DND bell, privacy dots, live activities and alerts stay reachable on Home (alerts are unchanged; they show only while the card is closed).
- R9. IPC `open <page>` accepts `home`, `music`, `agents`, `system`, `more`, `shots`, `messages`, `dayflow` and `settings`; `now` is kept as an alias for `home`. `state` reports the open page and the chip row.
- R10. Settings gains toggles for Weather, Agents, Messages, Dayflow and Shots (default on); off hides the page or field and stops its reads.

### Acceptance Examples

- AE1. Clean machine with no herdr, no Claude sessions, no media player, no Blip, no Dayflow, no snapdex: chips are Home, System, More; More lists Settings only.
- AE2. Media playing, herdr detected, Blip has 2 unread: chips are Home, Music, Agents, System, Messages, More (6).
- AE3. Same as AE2 plus Dayflow recording: still 6 chips; Dayflow stays under More.
- AE4. Card open on Home, then a new activity starts: Home's height does not change until the card closes and reopens (or the page changes).
- AE5. `qs ipc call island open agents` opens the card on Agents; `open now` opens Home.

### Scope Boundaries

- No approve/deny for agent permission prompts (needs a hook socket; follow-up).
- No new network egress. Weather reuses Omarchy's own `omarchy-weather-status` command, which queries the same wttr.in service Omarchy's bar weather already polls; it runs only when Omarchy's weather widget is in the bar.
- Shots, Messages and Dayflow detail views are simple lists; no thumbnails, no message text, no Dayflow controls.
- No change to the hover state machine, mask rules, alerts or pill.
- Page order and chip customization are not configurable in this PR.

## Planning Contract

### Key Technical Decisions

- KTD1. **One pure page registry.** `Pages.js` exports `PAGE_IDS`, `normalize(id)` (aliases `now` to `home`, unknown to `""`), and `chips(avail, live)` returning `{ chips: [ids], more: [ids] }`. `avail` says which pages are detected; `live` which More pages have something live. Base chips are home, music, agents, system (filtered by `avail`), then promoted pages in order messages, shots, dayflow while `chips.length < 5` (leaving room for More), then more. `more` lists the detected More pages in fixed order plus settings. A page that is not detected is never shown or reachable by click; IPC `open` for an undetected page falls back to home.
- KTD2. **Committed height for every page.** `Presentation.cardHeight(m)` drops the media-only special case: `h = band + pad + content + gap + pageRowH + pad`, floored at `min` (a minimum content height so short pages read as a card, not a strip) and capped at `max`. `content` is the active page component's `implicitHeight`, read once by `IslandWindow.commitCard()` on open and on page change, exactly as the media view does today. Settings keeps the full height because its content is that tall. The hot-zone rule (never shrinks while open) is unchanged.
- KTD3. **Chip set frozen while open.** The chip row is recomputed at commit time only (same commit as the height), so a page that becomes live while the card is open does not shift chips under the pointer. A frozen chip whose page later loses its backend still opens and shows its empty state.
- KTD4. **Read-only helpers, single-flight, polled only while relevant.** `bin/island-status <section>` prints JSON for `home` (battery, tailscale, vpn), `system` (battery, power profile, fan mode, cpu, memory, network, tailscale) and `more` (dayflow, shots). `bin/island-agents` prints normalized sessions. Both are Python 3 stdlib only, take `--root` for fixture trees, run each external command with a timeout, and never write. QML runs `home` and `more` once per card open, `system` every 2 s while the System page is visible, and `agents` once per open plus every 3 s while Agents is visible. Blip's `state.json` is read through a watched `FileView` (local file, no process).
- KTD5. **Detection at load, re-checked per open.** Agents is detected when the probe finds `herdr-app` or `~/.claude/sessions` exists; Messages when Blip's state file exists; Dayflow when `dayflow` is on PATH; Shots when `snapdex-ctl` exists (on PATH or in the snapdex plugin's `bin/`); Music when the media activity is active. Each is gated by its setting (R10).
- KTD6. **Agents focus through Hyprland.** The helper resolves a window address for each session: herdr sessions use the `herdr-app` client window; Claude sessions walk the session pid's parent chain (via `/proc/<pid>/stat`) to the first pid that owns a Hyprland client. The card runs `hyprctl dispatch 'hl.dsp.focus({ window = "address:0x..." })'` as one argv element (Omarchy's Dock uses the same form); herdr rows first run `herdr-app do agent.focus --terminal <id>` (the archived notch's form). A session with no window (Claude background sessions) has no action.
- KTD7. **Status vocabulary.** Agents.js maps herdr `blocked` and Claude `waiting`/`needs_input`/`blocked` to "needs you", herdr `working` and Claude `busy` to "working", `done` to "done", everything else to "idle"; order needs you, done, working, idle, then name.
- KTD8. **Weather reuses Omarchy's command.** `Weather.js` parses `omarchy-weather-status` output (`Place · Temp 12°C · Wind 10 km/h`) into `{ place, temp }`; the Home page runs it at most once per 30 minutes, only while Home is shown and only when `omarchy.weather` appears in the shell.json bar layout and the weather setting is on. "Weather unavailable" or junk hides the field.
- KTD9. **Quick toggles reuse existing paths.** DND uses the existing `DndSource.toggle()` (Omarchy's command). Mic mute runs `wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle` when the probe found `wpctl`; its state comes from the existing `PrivacySource` mute watch when available, otherwise `wpctl get-volume @DEFAULT_AUDIO_SOURCE@` read on open.
- KTD10. **Bottom row keeps DND visible.** The bottom row holds the chips, a compact DND bell toggle (glyph only, so six chips fit in the 720 px card) and Pin. The DND bell in Home's header and the privacy dots stay as today.

### High-Level Technical Design

```text
open / page change
  -> IslandWindow.commitCard()
       chips  = Pages.chips(avail, live)          (frozen while open)
       page   = Pages.normalize(page) or home
       height = Presentation.cardHeight({ content: card.contentHeight(page), ... })
  -> Card shows the page component; sources for that page start

sources (single-flight Process, only while relevant)
  bin/island-status home    -> Home.js   -> battery / tailscale / vpn dots
  omarchy-weather-status    -> Weather.js -> "12°C" (30 min cache, bar weather only)
  bin/island-status system  -> System.js -> System page rows (2 s while visible)
  bin/island-agents         -> Agents.js -> ordered rows + focus target
  bin/island-status more    -> More.js   -> dayflow / shots live flags
  FileView ~/.local/state/blip/state.json -> More.js -> unread counts
```

### Assumptions

- Claude Code session files carry `pid`, `name`, `cwd`, `kind` and `status`; observed statuses are `busy` and `idle`. A needs-input status string is not observed; the plan maps the plausible names (`waiting`, `needs_input`, `blocked`) and treats anything else as idle.
- `herdr-app ls` JSON shape matches the archived notch's `Agents.js` description (spaces, tabs, terminals with `terminal`, `app`, `status`, `sub_agents`).
- `snapdex-ctl` is not installed on omarchy-max, so Shots is hidden here and fixture-tested only.
- `powerprofilesctl` currently times out on omarchy-max; the System page hides the profile row when it fails.
- The fan helper's mode file (`$XDG_RUNTIME_DIR/omarchy-fan/current_fan_mode`) is absent here; the fan row is hidden.
- `omarchy-shell shell toggle lukedaduke.fan` reaches the fan panel through the shell's CLI IPC, which is not subject to the plugin API's ownership check.
- The owner accepts six chips while a page is promoted (session decision, supersedes P1 R16's five).

### Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Six chips plus DND and Pin overflow narrow screens | Chips shrink to labels only; DND becomes a glyph; the row is clipped, never wrapped; checked at 720 px |
| Content height read before a page's data arrives makes a short card | Each page sizes from a fixed skeleton (row count from data known at commit, minimum height floor) and elides; data arriving later never resizes |
| Polling costs CPU | Sources run only while their page is visible (System, Agents) or once per open (Home, More); helpers are single-flight with timeouts |
| `hl.dsp.focus` steals focus unexpectedly | Only on an explicit click; never automatic |
| Weather adds egress | Uses Omarchy's command against the service Omarchy's bar already polls, only when that widget is in the bar, at most twice an hour |
| Merge conflict with other Island worktrees | This branch is the only open Island PR; others are merged |

## Implementation Units

### U1. Page registry

- **Goal:** `Pages.js` decides which chips show, what More lists, and normalizes page ids.
- **Requirements:** R1, R2, R9; KTD1, KTD3.
- **Files:** `plugins/io.github.duketopceo.island/Pages.js` (new), `tests/test_island_pages.py` (new).
- **Approach:** Pure ES5, CommonJS export guard as in `Calendar.js`.
- **Test scenarios:** AE1, AE2, AE3 chip lists; promotion order Messages > Shots > Dayflow; never more than 6 chips; an undetected page is never promoted even if `live` says so; `normalize("now") === "home"`, unknown -> `""`; More always includes settings last.
- **Verification:** `pytest tests/test_island_pages.py` green after red.

### U2. Committed height for all pages

- **Goal:** One height rule for every page.
- **Requirements:** R7; KTD2.
- **Files:** `plugins/io.github.duketopceo.island/Presentation.js`, `tests/test_island_presentation.py`, `tests/test_island_nowplaying.py` (update media expectations).
- **Test scenarios:** height = band + pad + content + gap + pageRowH + pad for any page; floored at `min`; capped at `max`; the media case still yields the #78 height for the same inputs; non-numeric inputs are 0.
- **Verification:** presentation and nowplaying tests green.

### U3. Status helper and Home, System, Weather formatting

- **Goal:** `bin/island-status` reads battery, power profile, fan mode, CPU, memory, network, Tailscale, VPN, Dayflow and Shots; `Home.js`, `System.js`, `Weather.js` turn that into display rows.
- **Requirements:** R3, R6; KTD4, KTD8.
- **Files:** `plugins/io.github.duketopceo.island/bin/island-status` (new), `Home.js`, `System.js`, `Weather.js` (new), `tests/test_island_status_helper.py`, `tests/test_island_home.py`, `tests/test_island_system.py` (new).
- **Approach:** CPU from two `/proc/stat` reads 250 ms apart; memory from `/proc/meminfo` (MemTotal, MemAvailable); battery from `sys/class/power_supply/*/{type,capacity,status}`; network from `/sys/class/net/*/operstate` plus `nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device` when present; VPN from up interfaces named `wg*`, `tun*`, `nordlynx`, `proton*` (not `tailscale0`); Tailscale from `tailscale status --json` (BackendState, Self.Online, peer count only); Dayflow from `dayflow status --json` (capture_state, paused, frames_today, last_frame, storage_text); Shots from `snapdex-ctl` presence and `~/Pictures/Screenshots/index.md` (newest names and captions). Every command has a timeout and its absence yields `null` for that field.
- **Test scenarios:** fixture tree with battery, meminfo, two proc/stat snapshots (via an injectable stat sequence), net interfaces incl. `wg0` and `tailscale0`; missing tools -> nulls, exit 0; junk JSON from a stub tool -> null field; Weather parses Omarchy's format and rejects "Weather unavailable"; Home dots text (battery "80%", Tailscale "up"/"down"/hidden, VPN shown only when on); System rows hide null fields.
- **Verification:** helper and formatter tests green; helper run live prints valid JSON in under 1 s.

### U4. Agents

- **Goal:** List herdr and Claude Code sessions, needs-input first, with a focus target.
- **Requirements:** R5; KTD6, KTD7.
- **Files:** `plugins/io.github.duketopceo.island/bin/island-agents` (new), `Agents.js` (new), `tests/test_island_agents.py` (new).
- **Approach:** Helper flattens herdr terminals (and sub-agents) that have an app or status, reads Claude session files (only `pid`, `name`, `cwd` basename, `kind`, `status`; skips dead pids), resolves window addresses from `hyprctl clients -j`, and prints `{ ok, sessions: [{ source, id, app, name, where, status, terminal?, address? }] }`. `Agents.js` normalizes status, orders, labels ("Claude · wisp · needs you"), and builds the focus argv lists.
- **Test scenarios:** herdr fixture JSON -> blocked first; Claude session with dead pid skipped; pid chain resolves to the window owner; no herdr and no sessions -> `{ ok: true, sessions: [] }`; focus argv uses `hl.dsp.focus({ window = "address:0x..." })` as one element and never a shell string; address without `0x` gets it.
- **Verification:** tests green; helper live output lists herdr sessions here.

### U5. More sources

- **Goal:** Messages, Dayflow and Shots detection, live flags and list rows.
- **Requirements:** R2; KTD4, KTD5.
- **Files:** `plugins/io.github.duketopceo.island/More.js` (new), `tests/test_island_more.py` (new).
- **Approach:** `More.js` parses Blip `state.json` (unreadCounts, groups; counts only, no message text), Dayflow status, and the Shots list with an in-memory seen marker (newest name seen on the Shots page; first read sets the baseline).
- **Test scenarios:** unread total and per-chat rows with group names; muted chats excluded from the live flag; Dayflow live when recording or paused, not when stopped or missing; Shots unseen after a new newest name, cleared by `markSeen`.
- **Verification:** tests green.

### U6. Pages in the card, IPC and settings

- **Goal:** Card renders the pages; IPC opens them; settings toggles.
- **Requirements:** R1-R10; KTD2, KTD3, KTD9, KTD10.
- **Files:** `Card.qml`, `IslandWindow.qml`, `Island.qml`, `Settings.js`, `SettingsPage.qml`, new `HomePage.qml`, `MusicPage.qml`, `AgentsPage.qml`, `SystemPage.qml`, `MorePage.qml`, `ListPage.qml` (shared simple list for Shots, Messages, Dayflow), new sources `StatusSource.qml`, `AgentsSource.qml`, `MoreSource.qml`, `WeatherSource.qml`; `tests/test_island_settings.py`, `tests/test_island_window_logic.py` (page ids).
- **Approach:** Card keeps `heightFor()` but asks the visible page for `implicitHeight`; window freezes `chips` at commit; Home builds its strip from `layout.top` plus `layout.rows` (calendar first), media row click opens Music; Music hosts the existing header row and `MediaBlock`; DND bell glyph in the bottom row; root exposes `pageAvail`, `pageLive`, `toggleMicMute()`, `focusAgent(session)`, `openFanPanel()`.
- **Test scenarios:** Settings defaults include the five new booleans; window-logic tests accept the new page ids and alias `now`.
- **Verification:** `REQUIRE_QMLLINT=1 scripts/check-qml-syntax.py` clean; live: each page via `open <page>` plus screenshot.

### U7. Docs, data lifecycle, version

- **Files:** `plugins/io.github.duketopceo.island/README.md`, `docs/data-lifecycle.json`, `plugins/io.github.duketopceo.island/manifest.json`, `catalog.json`.
- **Approach:** New data surfaces `island_tailscale_status`, `island_agents`, `island_messages_counts`, `island_dayflow_status`, `island_weather`, `island_system_stats`; version 0.4.0 in manifest and catalog together.
- **Verification:** `check-data-lifecycle`, `validate-manifests`, `check-plugin-contract`, `check-release-readiness`, `check-scorecard` pass.

## Verification Contract

- Tests written first for every pure module and helper (observe red, then green). Node is called by the absolute `shutil.which("node")` path with `env={**os.environ, ...}`; PATH is never replaced.
- Gates: validate-manifests, check-plugin-contract, check-release-readiness, check-scorecard, check-data-lifecycle, `REQUIRE_QMLLINT=1` check-qml-syntax, ruff E9/F63/F7/F82, full pytest.
- Live (owner's desktop): back up the 0.3.2 install, link the worktree plugin, open each page through IPC and screenshot it, test DND and mic-mute toggles once each and restore, test one Agents focus and restore focus, then install a copy from the branch head. No pointer movement, no `island-hover-check`.

## Definition of Done

- PR open against `main` with CI green; plan, tests and gates as above; screenshots per page; 0.4.0 installed live as a copy of the branch head.
