---
title: Island Calendar Next-Event and Hover Intent - Plan
type: feat
date: 2026-11-16
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
origin: docs/plans/2026-11-14-feat-island-plan.md
execution: code
---

# Island Calendar Next-Event and Hover Intent - Plan

## Goal Capsule

- **Objective:** The Island tells Luke when his next meeting starts and lets him join it in one click, and it stops opening when the pointer merely passes over the top of the screen.
- **Means:** A read-only calendar helper (`bin/island-calendar`) that normalizes whichever calendar source the machine has into one JSON shape, a pure `Calendar.js` that turns it into an activity, and a pure `Intent.js` pointer-speed filter that `Hover.js` consults when its open timer fires.
- **Authority:** P1 Key Decisions KTD2, KTD3 and KTD4 (origin) win on hover mechanism; this plan's KTDs win on calendar and intent mechanism.
- **Stop conditions:** Stop if the intent filter would need the input mask to change outside commit points (origin KTD2), a second hover source (origin KTD3), or open/close rules outside `Hover.js` (origin KTD4). Stop if any calendar source can only be read by writing to it or by a new network call from the Island itself.
- **Execution profile:** Quickshell QML plus ES5 modules tested with node through pytest; Python helper tested with pytest fixtures. Live hover checks deferred to install (another agent owns the live install).
- **Who finishes:** One PR, `feat/island-calendar-intent`, off `main` (00f7fc9); version 0.3.2. Expected to merge after the Now Playing PR (0.3.1).

## Product Contract

### Summary

Two items from the notch-apps gap analysis (ranks 2 and 9): a next-calendar-event activity with a countdown and Join button, and a hover-intent speed filter.

### Problem Frame

A meeting reminder in the Island is high-value and cheap, since every macOS notch app shows one; the Island has no calendar surface. Separately, the hot zone sits where the pointer often crosses (bar, titlebars), and a dwell-only rule opens the card when a pass is slow enough to exceed `openDelay`.

### Requirements

- R1. When the next timed event starts within 10 minutes, the ear shows a countdown ("in 8m"); once it has started, "now" until 10 minutes past its start or its end, whichever is first.
- R2. While any event is due in the next 24 hours, the card's Now page shows it as a row: title and local start time ("Standup · 09:30").
- R3. When the event has a Zoom, Google Meet or Microsoft Teams https URL, the row and ear block offer Join, which opens it with `xdg-open`.
- R4. Source detection order: Omarchy's calendar data (`~/.local/state/omarchy/calendar-events.json`, written by the tmn73.calendar sync), `khal`, `gcalcli`, evolution-data-server. When none exists the activity stays hidden.
- R5. Read-only. Polled once per minute (once per 10 minutes while no source is detected), next 24 hours only. No new network calls from the Island (a source's own tool may sync as it already does).
- R6. A `calendar` setting toggle, default on; off stops the poll.
- R7. A pointer passing quickly over the hot zone does not open the card; a pointer that arrives and rests opens it after `openDelay` as today.
- R8. The P1 hover contract (origin KTD2, origin KTD3, origin KTD4) and `bin/island-hover-check`'s scripted opens still hold.

### Acceptance Examples

- AE1. **Covers R1, R2.** Given an event "Standup" at 09:30 and now 09:22, the ear reads "in 8m" and the card row reads "Standup · 09:30".
- AE2. **Covers R3.** Given the event's location holds `https://meet.google.com/abc-defg-hij`, the row shows Join; pressing it runs `xdg-open` with that URL.
- AE3. **Covers R4.** On a machine with none of the sources, the helper reports `source: "none"` and no calendar activity appears.
- AE4. **Covers R7.** A pointer moving across the pill at about 1 px/ms that is still moving when the 140 ms open timer fires does not open the card until it stops; a pointer that stops on the pill opens it after `openDelay` as today.

### Scope Boundaries

- No writing, RSVP or event creation. No all-day events in the ear (all-day events never count as "next").
- No media files (MediaSource.qml, media card, art, equalizer, lyrics): the Now Playing PR owns them.
- No per-app quiet list (the other half of gap 9).

#### Deferred to Follow-Up Work

- Live hover check (`bin/island-hover-check`) and live calendar render on omarchy-max: after this branch is installed.

## Planning Contract

### Key Technical Decisions

- KTD1. **One helper normalizes all sources.** `bin/island-calendar` (Python, stdlib only) detects the first available source and prints `{ source, events: [{ title, start, end, url }] }` with epoch-ms times, sorted, next 24 h, at most 5 events; the helper drops all-day and past events. A source counts as detected only when it yields at least one upcoming event; otherwise detection falls through to the next source, and an existing but empty Omarchy file is reported only when no later source exists. Meeting-URL extraction lives in the helper (scans url, location, description fields) and matches the parsed hostname, not a substring: https only, no userinfo, exact `meet.google.com`, `teams.microsoft.com`, `teams.live.com`, or `zoom.us` and its dot-suffix subdomains. `Calendar.js` repeats the https-plus-allowlist check before it emits `url`. QML never parses calendar formats.
- KTD2. **Calendar is an ordinary activity.** `Calendar.js` returns `{ id: "calendar", priority: 40, ... }`; outside the 10-minute window it is `cardOnly` (card row only, like Bluetooth), inside it competes for the ear. Join is the row's primary control via `Glyphs.primaryControl` and one isolated button in `ActivityBlock.qml` when the calendar is the top activity, both routed through the root's `act(id, action, value)` in `Island.qml` (the same entry point IPC uses).
- KTD3. **Detect-and-hide with slow re-detect.** When the helper reports `none`, the source polls every 10 minutes instead of every minute, so installing a calendar later is picked up without a restart.
- KTD4. **Intent is a gate on the open timer, not a new state.** `Intent.js` keeps the last motion samples (position + time, capped) and answers `moving(samples, now)`: true when the pointer covered more than the speed threshold (0.5 logical px/ms) over the last 80 ms. The window clears samples on leave and on every zone commit (hot-zone-local coordinates shift when the zone changes) and passes `moving` on the open-timer event; `Hover.js` re-arms a short 40 ms recheck instead of opening while it is true. Leave still cancels arming. The mask, the single HoverHandler and the rest of the state machine are unchanged (origin KTD2, KTD3, KTD4).
- KTD5. **No new hover setting.** The threshold is a constant; `openDelay` stays the owner's dial. A resting pointer produces no motion samples, so it is never "moving".

### High-Level Technical Design

Calendar data flow (directional):

```text
calendar source (omarchy json | khal | gcalcli | EDS)
  -> bin/island-calendar (detect, read, normalize, extract URL)  [every 60 s; 600 s when none]
  -> CalendarSource.qml (Process, parse JSON, minute tick)
  -> Calendar.activity(events, now) -> root activities list -> Activity.layout()
  -> ear text "in 8m" / card row "Title · 09:30" + Join -> act("calendar","join") -> xdg-open URL
```

Open-timer gate (directional):

```text
enter -> arming (timer openDelay)
timer fires: pointer inside?  no  -> closed
             moving (Intent)? yes -> stay arming, recheck in 40 ms
                              no  -> open
leave while arming -> closed (unchanged)
```

### Assumptions

- `~/.local/state/omarchy/calendar-events.json` is written by `omarchy-calendar-sync-all` (which calls the tmn73.calendar sync binary) as `{ version, syncedAt, source, events }`; the helper also tolerates a bare list. Its events carry `title`, `start`, `end` and optionally `dateKey`, `allDay`, `location`, `description`, `url`/`hangoutLink`/`conferenceUrl`; `start`/`end` are ISO 8601 datetimes or `HH:MM` with `dateKey`. The tmn73.calendar plugin is not installed on omarchy-max, so the file exists with zero events and the event field names are unverified; parsing is fixture-tested against this assumed shape.
- `khal list --json` field output and `gcalcli agenda --tsv` header output are parsed tolerantly from documented formats; neither tool is installed here, so both are fixture-tested only. EDS uses GObject introspection (`ECal`) when importable; it is not installed here and is untested live.
- 0.5 px/ms over 80 ms separates a pass from an arrival: a human pass across a 200 px pill runs 1 to 3 px/ms, and an arriving pointer decelerates to near zero.

### Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Intent gate delays the hover-check's scripted opens | Recheck at 40 ms; the scripted moves end at rest, so the gate releases within one 80 ms window, inside the check's 400 ms allowance |
| A slow, steady drift across the pill still opens | Accepted: slow movement reads as intent by design (AloeNotch) |
| Calendar helper hangs on a slow tool (gcalcli syncs over network) | Helper deadline 8 s; Process is single-flight |
| Merge conflict with the Now Playing PR in Island.qml, ActivityBlock.qml, Settings.js, manifest, catalog | Additions are isolated lines; version bump noted in the PR body |
| A calendar invite carries a lookalike meeting URL that Join would open | Parsed-hostname allowlist in the helper and again in `Calendar.js`; URL passed to `xdg-open` as one argv element, no shell |

## Implementation Units

### U1. Hover intent filter

- **Goal:** R7, R8.
- **Requirements:** R7, R8; KTD4, KTD5; origin KTD2, KTD3, KTD4.
- **Dependencies:** none.
- **Files:** `plugins/io.github.duketopceo.island/Intent.js` (new), `plugins/io.github.duketopceo.island/Hover.js`, `plugins/io.github.duketopceo.island/IslandWindow.qml`, `tests/test_island_intent.py` (new), `tests/test_island_hover.py`.
- **Approach:** Pure ES5 `Intent.js` with `add(samples, x, y, t)` (keeps samples within 150 ms, at most 8) and `moving(samples, now)`. `Hover.js` timer event accepts `moving`; when the open timer fires inside the zone with `moving === true`, it stays `arming` and returns a 40 ms timer. `IslandWindow.qml` feeds `hoverHandler.point.position` with `Date.now()` on point changes, clears samples on leave and on each zone commit, and passes `moving` on the timer event.
- **Execution note:** Test-first; observe the new tests fail before changing `Hover.js`.
- **Test scenarios:** `moving` true for samples crossing 200 px in 100 ms ending now; false when the last sample is older than 80 ms; false for 0.2 px/ms drift; false for one sample; `add` caps and trims old samples. Hover: `enter, timer{hovered, moving:true}` stays arming with timer 40; then `timer{moving:false}` opens; `enter, timer{moving:true}, leave` closes; timer without `moving` opens as before (back-compat); close and summon timers ignore `moving`.
- **Verification:** node-backed pytest green; existing hover tests unchanged and green.

### U2. Calendar helper

- **Goal:** R4, R5, R3 (URL extraction).
- **Requirements:** R3, R4, R5; KTD1.
- **Dependencies:** none.
- **Files:** `plugins/io.github.duketopceo.island/bin/island-calendar` (new), `tests/test_island_calendar_helper.py` (new).
- **Approach:** Detect in order: Omarchy JSON file exists, `khal` on PATH, `gcalcli` on PATH, `ECal` importable. `--root DIR` and `--now EPOCH` for tests (fixture HOME and fake tools on PATH, as `island-probe` tests do). Read-only subprocess calls with a deadline; never print event text to stderr.
- **Test scenarios:** Omarchy wrapper fixture with ISO and `dateKey`+`HH:MM` events returns sorted events inside 24 h, drops past and all-day; Meet/Zoom/Teams URLs extracted from location/description; http, `meet.google.com.evil.example`, `zoom.us@evil.example` and other hosts rejected; empty Omarchy file plus a fake `khal` yields `source: "khal"`; empty Omarchy file alone yields `source: "omarchy"`, no events; no sources yields `source: "none"`; fake `khal` and fake `gcalcli` outputs parse; a hanging fake tool hits the deadline and yields an error field, exit 0.
- **Verification:** pytest green; run by hand on omarchy-max reports the source it finds.

### U3. Calendar activity, wiring, setting

- **Goal:** R1, R2, R3, R6.
- **Requirements:** R1, R2, R3, R6; KTD2, KTD3.
- **Dependencies:** U2.
- **Files:** `plugins/io.github.duketopceo.island/Calendar.js` (new), `plugins/io.github.duketopceo.island/CalendarSource.qml` (new), `plugins/io.github.duketopceo.island/Glyphs.js`, `plugins/io.github.duketopceo.island/ActivityBlock.qml`, `plugins/io.github.duketopceo.island/Island.qml`, `plugins/io.github.duketopceo.island/Settings.js`, `plugins/io.github.duketopceo.island/SettingsPage.qml`, `tests/test_island_calendar.py` (new), `tests/test_island_glyphs.py`, `tests/test_island_settings.py`.
- **Approach:** `Calendar.js` picks the next non-all-day event whose end is in the future and builds the activity (ear text, card text, `url`, `cardOnly` outside the window). `CalendarSource.qml` runs the helper on a 60 s or 600 s timer, single-flight, and ticks `now` each minute. Join: `Glyphs.primaryControl` returns `"join"` for a calendar activity with a URL; label "Join"; root `act("calendar","join")` starts a detached `xdg-open` with the URL as one argv element.
- **Test scenarios:** AE1 countdown text at 8 m, "now" after start, card-only at 11 m; no event yields inactive; past-end event skipped for the next; time formatted HH:MM local; Join control present only with an allowlisted https URL (a lookalike host in the input yields no `url`); settings default `calendar: true` and non-boolean resolves to default.
- **Verification:** node-backed pytest green; qmllint clean.

### U4. Docs, data lifecycle, version

- **Goal:** Ship hygiene.
- **Requirements:** R5.
- **Dependencies:** U1-U3.
- **Files:** `plugins/io.github.duketopceo.island/README.md`, `plugins/io.github.duketopceo.island/manifest.json`, `catalog.json`, `docs/data-lifecycle.json`, `docs/reviews/io.github.duketopceo.island.md`.
- **Approach:** README rows for calendar and intent; data-lifecycle surface `island_calendar` (local read only, no egress, nothing retained); version 0.3.2; review doc notes live checks deferred.
- **Test expectation:** covered by the repo gates (`check-data-lifecycle.py`, manifests, release readiness).

## Verification Contract

- All repo gates from the brief: validate-manifests, check-plugin-contract, check-release-readiness, check-scorecard, check-data-lifecycle, `REQUIRE_QMLLINT=1` check-qml-syntax, ruff E9/F63/F7/F82, full pytest (test_fan_naming may fail host-dependently).
- Live, now: `bin/island-calendar` run by hand on omarchy-max.
- Live, deferred to install: `bin/island-hover-check` run, a fast-pass pointer sweep, and the calendar row render.

## Definition of Done

- U1-U4 landed in one PR against `main`, gates green, review findings applied or listed, PR body carries the merge-order note (after Now Playing 0.3.1) and the deferred live checks.
