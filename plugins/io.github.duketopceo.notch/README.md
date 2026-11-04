# Notch

A Mac-style notch island at the top center of every screen, for Omarchy 4.5.

- On MacBook panels with a camera cutout (from Omarchy's `display-cutouts.json`) it hugs the camera: time in the left ear, date in the right ear.
- On other screens it is a virtual notch with the same content on one line.
- The ear text hugs the camera (6 px gap: left ear right-aligned, right ear left-aligned) and the island is exactly the cutout height.
- Idle: clock and date, with the current weather sliding in every half minute. While music plays, the track title takes the right ear.

Weather comes from Open-Meteo (free, no key) for the place set in Omarchy's weather settings, fetched at most every 15 minutes by `bin/notch-data` into `~/.cache/omarchy/notch.json`.

## Hover expand

Hover the island for about 150 ms and it springs down into a panel with a tab strip. Leaving collapses it after about 300 ms. Click the island to pin it open; while expanded, a click anywhere outside (a transparent full-screen catcher on layer Top, present only while expanded, no keyboard focus) or Esc (when the panel has focus) collapses it. Logic lives in `Expand.js`, UI in `ExpandedPanel.qml`.

Panel size is per tab: a tab entry in `Tabs.js` may carry `size: { w, h }` (logical px); without it the panel is 460x240. Home is 720x380, Stocks 640x360 (clamped to the screen width minus 16, always centered). The island animates the size change when you switch tabs. The tab strip shows glyph + short label (`short` in `Tabs.js`) on equal-width chips when they all fit, else only the selected chip carries its label.

## Ears

The right ear grows for a long activity text (track title). Max ear width = base ear + the narrower side's free bar room (the same `room` as `bin/notch-layout-check`: `Model.sideRoom`) minus a 12 px margin, capped at 280; the island stays centered on the camera. Text still too long for that scrolls slowly (marquee) instead of eliding. `notch-layout-check` prints the current limit per scenario.

## Tabs

The expanded panel has a tab strip and a content area. Tabs are listed in `Tabs.js` as `{ id, title, glyph, source }`. The content is a `Loader` on `source` (a QML file next to `Notch.qml`) and the loaded item gets a `notch` property: the root `Notch.qml` item (declare `property var notch: null` in your tab). A tab whose file is missing shows "<Title> is coming soon", never an error.

Tabs:

- **Home**: date, weather with the pixel icon, now playing (compact), up to 2 quotes, the active app name, a month calendar, counters (agents working / need you / done, unread messages, top AI usage %) and status dots: Tailscale (click copies the IP), NordVPN (click toggles), Wisp (click opens its panel), Dictate (click runs `wordink dictation toggle`).
- **Media**, **Agents** (AI usage on top, wheel scroll about 3 rows per notch), **Messages** (Blip threads, read-only), **Plugins**, **Settings** (scrollable).
- **Network** (`NetworkTab.qml`, `Network.js`, `NetworkState.qml`): Tailscale (state, this device's tailnet IP, peers with online/offline dots, connect/disconnect switch, click an IP to copy it) and NordVPN (state, country/server, connect/disconnect switch). `/usr/bin/tailscale up|down` and the nordvpn plugin's own `probe_nordvpn.py connect|disconnect`. It polls every 8 s only while a tab showing it is visible, plus a cheap status read (no peer list) every 60 s that drives the small status dot on the idle notch (green when either is up, amber while connecting).
- **Screenshots** (optional, Settings > "Screenshots (snapdex)", off by default): last 8 thumbnails with captions, unprocessed count, "Process now", the Auto switch and "Open folder", all through the snapdex plugin's `snapdex-ctl`. Shots are saved to and renamed in `~/Pictures/Screenshots`. While on, a newly captioned screenshot flashes its caption in the notch for 4 s at priority 30.

The Plugins tab opens a slot by trying the shell's `summon`, then the plugin's own `qs ipc call <id> toggle`, then a per-plugin fallback. Plugins in the bar's `tray` section only have a panel the shell can summon while their widget is live, which needs the built-in tray host (`omarchy.tray`, not disabled in `shell.json` `disabledPlugins`) on the bar; otherwise the slot says "not on the bar". The Stocks tab cards show today's change vs the previous close; the big chart header shows the selected range's change.

Click the right ear while a dictation shows to toggle dictation.

Useful `notch` members for tabs: `weather`, `now`, `textColor`, `dimColor`, `fontFamily`, `pluginDir`, `shellConfig`, `settings` (resolved), `setSetting(key, value)`, `openPlugin(id)`, `activities`.

### Plugins tab

One slot per plugin id in the bar's `tray` section (`shell.shellConfig`, else `~/.config/omarchy/shell.json` `bar.layout.tray`). Name and icon come from `~/.config/omarchy/plugins/<id>/manifest.json` (`barWidget.displayName` or `name`; `preview` as an image path or short glyph, else a generic glyph). Clicking a slot calls `shell.toggle(id, "{}")`, falling back to `qs ipc call shell toggle <id> {}`.

### Settings tab

Stored in this plugin's entry of `shell.json` `plugins[]` through `shell.mutateShellConfig`; missing values use defaults.

| key | default | meaning |
| --- | --- | --- |
| `clockSeconds` | 24 | idle clock hold, seconds |
| `slideSeconds` | 7 | each weather/stocks slide, seconds |
| `showWeather` / `showStocks` | true | idle slides on/off |
| `unit` | `"F"` | `"F"` or `"C"`; passed to `bin/notch-data --unit` |
| `clockHours` | 12 | 12 or 24 hour clock |
| `cameraWidth` | 0 | 0 = auto, else logical px |
| `hoverDelay` | 150 | ms before hover expands |
| `snapdex` | false | Screenshots tab and caption flash (needs the snapdex plugin) |

## Activity contract

The side text (right ear, or the virtual notch line) shows the highest-priority active activity, else the idle cycle. `Notch.qml` keeps one list:

```qml
readonly property var activities: [
  { id: "dictation", active: dictation.active, priority: 90, text: dictation.text },
  { id: "media", active: !!player, priority: 50, text: mediaText, glyph: "\u{F075A}" }
  // activities:end
]
```

Each entry is `{ id, active (bool), priority (int, higher wins), text (string), glyph? }`. Ties go to the earlier entry; entries with empty text are skipped. To add an `XActivity` (a `Scope` exposing `active` and `text`, like `WordinkActivity`), instantiate it in `Notch.qml` and add one line above the `activities:end` marker. Logic is in `Activity.js`.

## Slimming the bar

`bin/notch-slim-bar` removes the bar widgets the notch covers (Tailscale, NordVPN, snapdex, WordInk, finance, world clock, active window) from `shell.json` `bar.layout`. `--dry-run` shows the change, `--undo` puts the entries back. It backs up to `shell.json.bak-notch-v3` first and keeps `omarchy.indicators`, `omarchy.microphone`, Blip and Wisp. Tests: `tests/test_notch_slim_bar.py`.

## Checking the bar layout

`bin/notch-layout-check --expand` reads the live bar from the running shell and reports, per screen, every widget's section, position and spacing, whether the notch covers it, and whether it would once widgets grow (media playing, a long window title, the tray drawer open). It exits 1 when anything is blocked.

## Status

v0.1. Next: pixel-art weather icons, stock watchlist slide, WordInk dictation state, hover expand. See `docs/plans/2026-11-04-0215-feat-notch-island-plan.md`.

## NOTICE

The hover-expand design (timing, expand-downward behavior) takes its cues from omanotch, https://github.com/skuthus/omanotch. No code is copied; the notice is kept for the design reference.

MIT License. Copyright (c) 2026 skuthus

## Screenshots paths

The Screenshots tab reads `inbox` and `library` from `snapdex-ctl panel` JSON; when absent it uses `~/Pictures/Screenshots/Library` if it exists, else `~/Pictures/Screenshots`. "Open folder" opens the library; the inbox pending count is shown separately.
