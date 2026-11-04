# Notch

A Mac-style notch island at the top center of every screen, for Omarchy 4.5.

- On MacBook panels with a camera cutout (from Omarchy's `display-cutouts.json`) it hugs the camera: time in the left ear, date in the right ear.
- On other screens it is a virtual notch with the same content on one line.
- Idle: clock and date, with the current weather sliding in every half minute. While music plays, the track title takes the right ear.

Weather comes from Open-Meteo (free, no key) for the place set in Omarchy's weather settings, fetched at most every 15 minutes by `bin/notch-data` into `~/.cache/omarchy/notch.json`.

## Hover expand

Hover the island for about 150 ms and it springs down into a 460x240 panel with a tab strip. The Home tab holds: media controls (Mpris), today's date with a month calendar, a weather line, a quotes line when the cache has `quotes`, and status dots for Wisp (`$XDG_RUNTIME_DIR/wisp/state.json`) and NordVPN (the nordvpn plugin's read-only status probe, polled every 30 s only while open). Leaving collapses it after about 300 ms. Logic lives in `Expand.js`, UI in `ExpandedPanel.qml` and `MiniCalendar.qml`; `Notch.qml` carries only the `U5` hook lines.

## Tabs

The expanded panel has a tab strip and a content area. Tabs are listed in `Tabs.js` as `{ id, title, glyph, source }`. The content is a `Loader` on `source` (a QML file next to `Notch.qml`) and the loaded item gets a `notch` property: the root `Notch.qml` item (declare `property var notch: null` in your tab). A tab whose file is missing shows "<Title> is coming soon", never an error.

Shipped: Home (`HomeTab.qml`, the original panel), Plugins (`PluginsTab.qml`), Settings (`SettingsTab.qml`). Placeholders for `MediaTab.qml`, `AgentsTab.qml` and `MessagesTab.qml` light up as soon as those files exist.

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

## Checking the bar layout

`bin/notch-layout-check --expand` reads the live bar from the running shell and reports, per screen, every widget's section, position and spacing, whether the notch covers it, and whether it would once widgets grow (media playing, a long window title, the tray drawer open). It exits 1 when anything is blocked.

## Status

v0.1. Next: pixel-art weather icons, stock watchlist slide, WordInk dictation state, hover expand. See `docs/plans/2026-11-04-0215-feat-notch-island-plan.md`.

## NOTICE

The hover-expand design (timing, expand-downward behavior) takes its cues from omanotch, https://github.com/skuthus/omanotch. No code is copied; the notice is kept for the design reference.

MIT License. Copyright (c) 2026 skuthus
