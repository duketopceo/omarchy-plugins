# Notch

A Mac-style notch island at the top center of every screen, for Omarchy 4.5.

**Self-contained:** install this plugin alone on a clean Omarchy box and you get a usable island — clock/date, weather, hover expand with built-in tabs (Home, Media, Network, Power, System, Stocks, Plugins, Settings). First click opens **Settings** until you finish optional setup: `bin/notch-probe` detects screenshots / agents / messages / WordInk / Wisp / finance / fan (and GPU/NPU labels) and offers Enable for each. Nothing hard-depends on Luke’s private shell config or on other duketopceo plugins.

## Platform (honest)

| Environment | Support |
| --- | --- |
| **Omarchy on Linux** (x86_64 or aarch64) | **Yes** — this is the only target. Quickshell + Wayland. |
| **Omarchy on Apple Silicon** (Asahi / ARM Linux) | **Yes**, when Omarchy runs there: cutout geometry from `/usr/share/omarchy-platform/display-cutouts.json` + `/proc/device-tree/compatible`, ANE when `/sys/class/accel` exists. |
| **macOS / stock MacBook** | **No.** This is not a macOS app and cannot run in macOS. “MacBook” here means Linux Omarchy on that hardware (or any Linux laptop), not Apple’s OS. |

Display geometry auto-detects for any panel size Omarchy knows: model table (13–16″ Air/Pro codes), physical panel width table, then ~12% of physical width when a cutout matches but the model is unknown. Externals and notchless panels get a virtual island. Camera width override remains in Settings (`0` = auto).

## Install

From this umbrella repo:

```bash
./scripts/install.sh --link    # or --copy
# then enable io.github.duketopceo.notch in Omarchy plugin settings / shell.json
```

Or, once the mirror exists: `omarchy plugin add https://github.com/duketopceo/omarchy-notch`.

No other duketopceo plugins are required. Optional host tools (when present): `tailscale`, `nordvpn`, MPRIS players, `wordink`, Blip (`nixfred.blip`), herdr, snapdex, lukedaduke.fan.

## Setup (optional modules)

`bin/notch-probe` runs once at load and feeds the Settings strip:

| Module | Detects | Enable setting | Tab / surface |
| --- | --- | --- | --- |
| Screenshots | snapdex-ctl | `snapdex` | Shots tab |
| Agents | `herdr-app` | `optAgents` | Agents tab |
| Messages | Blip state/plugin | `optMessages` | Messages tab |
| Dictation | `wordink` CLI | `optWordink` | Home Dict + activity |
| Wisp | wisp plugin / runtime | `optWisp` | Home Wisp dot |
| Finance | finance.json / stocks.watchlist | `showStocks` | Idle stock slides (Stocks tab always built-in) |
| Fan modes | lukedaduke.fan / helper | `optFan` | System mode pills |

Built-in (always on): Home, Media, Network, Power, System, Stocks, Plugins, Settings. GPU/NPU on System are **labels from probe** (Asahi AGX / NVIDIA / AMD / Intel / none; ANE when present) — utilization is not claimed where the kernel does not expose it.

- On panels with a camera cutout (Omarchy's `display-cutouts.json`) it hugs the camera: time in the left ear, date in the right ear.
- On other screens it is a virtual notch with the same content on one line.
- The ear text hugs the camera (6 px gap: left ear right-aligned, right ear left-aligned) and the island is exactly the cutout height.
- Idle: clock and date, with the current weather sliding in every half minute. While music plays, the track title takes the right ear.

Weather comes from Open-Meteo (free, no key) for the place set in Omarchy's weather settings, fetched at most every 15 minutes by `bin/notch-data` into `~/.cache/omarchy/notch.json`. Stock quotes use Yahoo's public endpoints for the Omarchy finance watchlist (or this plugin's `stocks.watchlist` setting).

## Hover expand

Hover the island for about 150 ms and it springs down into a panel with a tab strip. Leaving collapses it after about 300 ms. Click the island to pin it open; while expanded, a click anywhere outside (a transparent full-screen catcher on layer Top, present only while expanded, no keyboard focus) or Esc (when the panel has focus) collapses it. Logic lives in `Expand.js`, UI in `ExpandedPanel.qml`.

Panel size is per tab: a tab entry in `Tabs.js` may carry `size: { w, h }` (logical px); without it the panel is 460x240. Home is 720x380, Stocks 640x360 (clamped to the screen width minus 16, always centered). The island animates the size change when you switch tabs. The tab strip shows glyph + short label (`short` in `Tabs.js`) on equal-width chips when they all fit, else only the selected chip carries its label.

## Ears

The right ear grows for a long activity text (track title). Max ear width = base ear + the narrower side's free bar room (the same `room` as `bin/notch-layout-check`: `Model.sideRoom`) minus a 12 px margin, capped at 280; the island stays centered on the camera. Text still too long for that scrolls slowly (marquee) instead of eliding. `notch-layout-check` prints the current limit per scenario.

## Tabs

The expanded panel has a tab strip and a content area. Tabs are listed in `Tabs.js` as `{ id, title, glyph, source }`. The content is a `Loader` on `source` (a QML file next to `Notch.qml`) and the loaded item gets a `notch` property: the root `Notch.qml` item (declare `property var notch: null` in your tab). A tab whose file is missing shows "<Title> is coming soon", never an error.

Tabs:

- **Home**: date, weather with the pixel icon, now playing (compact), up to 2 quotes, the active app name, a month calendar, counters when optional backends are enabled, status dots: Tailscale, NordVPN, Dictate / Wisp when opted in and detected.
- **Media**, **Plugins**, **Settings** (includes first-run optional setup).
- **Agents** / **Messages** / **Screenshots**: optional tabs — off until Setup Enable (or Settings toggles); probe offers them when herdr / Blip / snapdex are present.
- **Network**: Tailscale and NordVPN via `/usr/bin/tailscale` and `/usr/bin/nordvpn` only. Missing CLIs → Unavailable.
- **Power** / **System**: sysfs; GPU/NPU labels from probe; fan mode writes when `optFan` + lukedaduke.fan.
- **Stocks**: Yahoo via `bin/notch-data` (standalone).

The Plugins tab opens a slot by trying the shell's `summon`, then the plugin's own `qs ipc call <id> toggle`, then a per-plugin fallback. Plugins in the bar's `tray` section only have a panel the shell can summon while their widget is live, which needs the built-in tray host (`omarchy.tray`, not disabled in `shell.json` `disabledPlugins`) on the bar; otherwise the slot says "not on the bar". An empty tray is fine — the tab just says there are no tray plugins.

Useful `notch` members for tabs: `weather`, `now`, `textColor`, `dimColor`, `fontFamily`, `pluginDir`, `shellConfig`, `settings` (resolved), `setSetting(key, value)`, `openPlugin(id)`, `activities`.

### Plugins tab

One slot per plugin id in the bar's `tray` section (`shell.shellConfig`, else `~/.config/omarchy/shell.json` `bar.layout.tray`). Name and icon come from `~/.config/omarchy/plugins/<id>/manifest.json` (`barWidget.displayName` or `name`; `preview` as an image path or short glyph, else a generic glyph). Clicking a slot calls `shell.toggle(id, "{}")`, falling back to `qs ipc call shell toggle <id> {}`.

### Settings tab

Stored in this plugin's entry of `shell.json` `plugins[]` through `shell.mutateShellConfig`; missing values use defaults. No private config is required for first launch.

| key | default | meaning |
| --- | --- | --- |
| `clockSeconds` | 24 | idle clock hold, seconds |
| `slideSeconds` | 7 | each weather/stocks slide, seconds |
| `showWeather` / `showStocks` | true | idle slides on/off |
| `unit` | `"F"` | `"F"` or `"C"`; passed to `bin/notch-data --unit` |
| `clockHours` | 12 | 12 or 24 hour clock |
| `cameraWidth` | 0 | 0 = auto, else logical px |
| `hoverDelay` | 150 | ms before hover expands |
| `snapdex` | false | Screenshots tab (offer when snapdex detected) |
| `optAgents` / `optMessages` | false | Agents / Messages tabs |
| `optWordink` / `optWisp` / `optFan` | true | Home Dict / Wisp / System fan modes when backends exist |
| `setupDone` | false | First-run setup strip dismissed |

## Activity contract

The side text (right ear, or the virtual notch line) shows up to two active activities in priority order when they fit; otherwise it shows the highest-priority activity. When none are active, it shows the idle cycle. Clicking an activity opens its tab, or Home when that tab is unavailable. `Notch.qml` keeps one list:

```qml
readonly property var activities: [
  { id: "dictation", active: dictation.active, priority: 90, text: dictation.text },
  { id: "media", active: !!player, priority: 50, text: mediaText, glyph: "\u{F075A}" }
  // activities:end
]
```

Each entry is `{ id, active (bool), priority (int, higher wins), text (string), glyph? }`. Ties go to the earlier entry; entries with empty text are skipped. To add an `XActivity` (a `Scope` exposing `active` and `text`, like `WordinkActivity`), instantiate it in `Notch.qml` and add one line above the `activities:end` marker. Logic is in `Activity.js`.

## Slimming the bar

`bin/notch-slim-bar` removes the bar widgets the notch covers (Tailscale, NordVPN, snapdex, WordInk, finance, world clock, active window) from `shell.json` `bar.layout`. `--dry-run` shows the change, `--undo` puts the entries back. It backs up to `shell.json.bak-notch-v3` first and keeps `omarchy.indicators`, `omarchy.microphone`, Blip and Wisp. Optional helper for hosts that already had those widgets; not required for a fresh install. Tests: `tests/test_notch_slim_bar.py`.

## Checking the bar layout

`bin/notch-layout-check --expand` reads the live bar from the running shell and reports, per screen, every widget's section, position and spacing, whether the notch covers it, and whether it would once widgets grow (media playing, a long window title, the tray drawer open). It exits 1 when anything is blocked.

## Status

v0.1 with capability probe + first-run optional setup. Linux/Omarchy only (including Asahi when Omarchy runs there) — not macOS. See plan `docs/plans/2026-11-04-0215-feat-notch-island-plan.md`.

## NOTICE

The hover-expand design (timing, expand-downward behavior) takes its cues from omanotch, https://github.com/skuthus/omanotch. No code is copied; the notice is kept for the design reference.

MIT License. Copyright (c) 2026 skuthus

## Screenshots paths

The Screenshots tab reads `inbox` and `library` from `snapdex-ctl panel` JSON; when absent it uses `~/Pictures/Screenshots/Library` if it exists, else `~/Pictures/Screenshots`. "Open folder" opens the library; the inbox pending count is shown separately.
