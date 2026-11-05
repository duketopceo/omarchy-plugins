---
title: Notch island plugin - Plan
type: feat
date: 2026-11-04
topic: notch-island
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
status: planned
---

# Notch island plugin - Plan

## Goal Capsule

- **Objective:** turn the top-center of every screen into a Mac-style notch island that shows useful, calm information at a glance (clock first, then weather and a stock watchlist) and expands on hover, so the bar's crowded center can go away.
- **Means:** a new Omarchy 4.5 panel plugin, `io.github.duketopceo.notch`, with its own layer-shell window per screen. On a panel with a camera cutout it sizes itself from Omarchy's display-cutout data; on other screens it draws a virtual notch.
- **Ships first as v0.1:** the window on every screen, idle clock and date, and a weather slide. Everything else lands in later units.

## Product Contract

### Summary

A notch island on every screen. On the laptop it hugs the camera cutout and uses the space either side of the camera; on external monitors it is a slightly roomier virtual notch. While idle it shows the clock and date and every so often slides, with a small animation, to weather (tiny pixel-art icon) and then to the stock watchlist. Live activities (dictation, now playing) take over the idle cycle while they run. Hover expands it into media controls, calendar, full weather, the watchlist and small status dots. The widgets it absorbs leave the bar.

### Requirements

- R1. The island shows on every screen at top center. On a screen matched by `/usr/share/omarchy-platform/display-cutouts.json` its height follows the cutout (`top` rows scaled to logical px) and its content sits beside the camera, never under it. On other screens it is a virtual notch with content centered.
- R2. Idle content: clock and date most of the time; a timed cycle slides to weather, then to the watchlist, then back. The cycle period and order are settings.
- R3. Weather slide: current temperature plus a small animated pixel-art icon (4- to 8-bit look) for clear, cloudy, rain, snow, storm, fog, night.
- R4. Watchlist slide: symbols from the finance plugin's saved watchlist (`~/.local/state/omarchy/settings/finance.json` `watchlist`), price and day change, rotated a few at a time.
- R5. WordInk activity: recording, transcribing and error states from the `wordink` CLI take over the idle cycle.
- R6. Now playing takes over the idle cycle while media plays; hover shows controls.
- R7. Hover expands the island into: media controls, indicators, calendar, full weather, the watchlist, and Wisp and NordVPN status dots.
- R8. The island coexists with the Omarchy bar: it never covers the bar's left or right sections on any screen, and it never takes over `omarchy.notifications` or `omarchy.osd`.
- R9. The bar is slimmed to match: widgets the island absorbs are removed from `bar.layout` through a documented step that backs up `shell.json` first.

### Scope Boundaries

- Out: notifications and volume/brightness OSD (Omarchy keeps them); Hyprland keybindings or any stash-managed Hyprland file; sudo; voxtype polling; telemetry.
- Network: the island may fetch weather (Open-Meteo, no key) and quotes for the saved watchlist, cached, at a low rate. No other network use.
- Later: a file shelf / drop zone (boring.notch, NotchDrop style).
- Design cues come from boring.notch and Atoll (both GPL-3.0): behavior and look only, no code. Small pieces from omanotch (MIT) may be adapted with its notice kept.

### Success Criteria

- v0.1 is visible on every connected screen within seconds of enabling, with no QML errors in the shell journal and no bar overlap.
- Each later unit lands as its own PR with its tests passing.

## Planning Contract

### Key Technical Decisions

- KTD1. Build new on Omarchy 4.5 rather than fork. (session-settled: user-approved — chosen over forking omarchy-dynamic-island or omanotch: both size the notch by hand, use bare `Color.` that breaks on Qt 6.12, and fight the bar's own notch handling.)
- KTD2. Show content while idle. (session-settled: user-directed — chosen over a blank notch until hover.)
- KTD3. Show on every screen, virtual on externals. (session-settled: user-directed — chosen over laptop-only.)
- KTD4. Idle view is clock and date first, cycling to pixel-art weather and the stock watchlist. (session-settled: user-directed — chosen over a static clock.)
- KTD5. One `PanelWindow` per screen via `Variants { model: Quickshell.screens }`, `WlrLayer.Overlay`, `ExclusionMode.Ignore`, input mask on the island only, so the rest of the strip passes clicks through. This is the pattern omanotch uses for one screen, extended to all.
- KTD6. Cutout geometry reuses the bar's own parsing (`BarModel.parseCutouts` / `cutoutTop` logic, re-implemented in the plugin's `Model.js` since shell internals are not a public API). The cutout file gives only the height; the camera width is a setting with a default for the 14" and 16" panels, plus a calibration override.
- KTD7. Theme only through `import qs.Commons as Commons` (`Commons.Color`, `Commons.Style`); no bare `Color.` and no hardcoded hex, per the repo rules.
- KTD8. Pure logic (geometry, cycle scheduler, weather code to icon, quote formatting) lives in `Model.js` so it can be tested with node, in the style of the repo's existing tests.
- KTD9. Weather and quotes come from a small helper in `plugins/io.github.duketopceo.notch/bin/` that writes a JSON cache; the QML reads the cache with `FileView`. One fetch path, rate-limited, easy to test offline with fixtures.

### Assumptions

- The 16" camera is about 200 logical px wide at scale 2. To be checked on the panel during U1 and made a setting.
- The finance plugin keeps its watchlist at the path in R4.

## Implementation Units

### U1. v0.1: window, geometry, clock and weather slide

- Files: `plugins/io.github.duketopceo.notch/manifest.json` (kind `panel`, `keepLoaded`), `Notch.qml`, `Model.js`, `bin/notch-data` (weather fetch to cache), `README.md`, `AGENTS.md`, `LICENSE` (MIT), `tests/model.test.js`.
- Island per screen; cutout height from the cutout file; camera gap on cutout screens; virtual notch elsewhere.
- Idle cycle: clock and date, then weather (text icon in v0.1), then back.
- Test scenarios (`tests/model.test.js`): cutout match for 3456x2234 returns 32 logical px at scale 2; an external 5120x1440 screen returns 0; a rotated panel returns 0; the cycle scheduler returns clock most of the time and each slide in order; weather codes map to the right icon names; malformed cache JSON yields no weather slide instead of an error.

### U2. Pixel-art weather icons and slide animation

- Small sprite set (4- to 8-bit look) drawn with QML `Canvas` or tiny PNG sprites, with a 2-4 frame animation; slide transition between idle views.
- Tests: icon selection for day and night codes.

### U3. Stock watchlist slide

- Helper fetches quotes for the saved watchlist into the cache; slide rotates a few symbols with price and day change, colored by direction.
- Tests: quote parsing from a fixture, formatting of price and change, rotation order.

### U4. WordInk and now playing activities

- WordInk: follow `wordink logs -f` for state changes, with `wordink status --json` as the fallback check when it is not running (same approach as the WordInk bar plugin). States: recording, transcribing, error.
- Now playing: `Quickshell.Services.Mpris` active player; activities take over the idle cycle by priority.
- Tests: event-to-state mapping from fixture lines; priority order.

### U5. Hover expand

- Expanded view: media controls, indicators, calendar, full weather, watchlist, Wisp and NordVPN dots. Reads existing state where it is public (Mpris, Wisp state file); no takeover of other plugins.
- Tests: expand/collapse state machine.

### U6. Bar slimming, docs, catalog, mirror repo

- `scripts/notch-slim-bar.py`: backs up `shell.json`, removes the absorbed widgets from `bar.layout`, can undo.
- Catalog entry, `validate-manifests.py`, README with screenshots, `scripts/publish.sh` to the standalone mirror repo.
- Tests: slimming script on a fixture `shell.json` (removes the right ids, keeps the rest, undo restores).

## Verification

- `node tests/model.test.js` (or the repo's test runner) passes.
- `python scripts/validate-manifests.py` passes.
- Live check per unit: the shell journal shows no errors from the plugin; a screenshot of the top of each screen shows the island centered, clear of the camera, and not covering the bar sections.

## Risks

- Qt 6.12 and private `qs.Commons` APIs may shift again; keep all theme access in one place.
- The island overlapping bar sections on narrow screens; U1 keeps it narrow, and U6 removes the center widgets.
- A QML error in a keepLoaded panel can disturb the shell; test each unit with a shell restart before merging.
