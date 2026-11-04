# Notch

A Mac-style notch island at the top center of every screen, for Omarchy 4.5.

- On MacBook panels with a camera cutout (from Omarchy's `display-cutouts.json`) it hugs the camera: time in the left ear, date in the right ear.
- On other screens it is a virtual notch with the same content on one line.
- Idle: clock and date, with the current weather sliding in every half minute. While music plays, the track title takes the right ear.

Weather comes from Open-Meteo (free, no key) for the place set in Omarchy's weather settings, fetched at most every 15 minutes by `bin/notch-data` into `~/.cache/omarchy/notch.json`.

## Hover expand

Hover the island for about 150 ms and it springs down into a 420x180 panel: media controls (Mpris), today's date with a month calendar, a weather line, a quotes line when the cache has `quotes`, and status dots for Wisp (`$XDG_RUNTIME_DIR/wisp/state.json`) and NordVPN (the nordvpn plugin's read-only status probe, polled every 30 s only while open). Leaving collapses it after about 300 ms. Logic lives in `Expand.js`, UI in `ExpandedPanel.qml` and `MiniCalendar.qml`; `Notch.qml` carries only the `U5` hook lines.

## Checking the bar layout

`bin/notch-layout-check --expand` reads the live bar from the running shell and reports, per screen, every widget's section, position and spacing, whether the notch covers it, and whether it would once widgets grow (media playing, a long window title, the tray drawer open). It exits 1 when anything is blocked.

## Status

v0.1. Next: pixel-art weather icons, stock watchlist slide, WordInk dictation state, hover expand. See `docs/plans/2026-11-04-0215-feat-notch-island-plan.md`.

## NOTICE

The hover-expand design (timing, expand-downward behavior) takes its cues from omanotch, https://github.com/skuthus/omanotch. No code is copied; the notice is kept for the design reference.

MIT License. Copyright (c) 2026 skuthus
