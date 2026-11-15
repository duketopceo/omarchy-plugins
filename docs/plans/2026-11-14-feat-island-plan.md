---
title: Island — the one top-of-screen surface for Omarchy (fresh build)
date: 2026-11-14
type: feat
artifact_contract: ce-unified-plan/v1
execution: code
status: active
supersedes:
  - archive/notch/docs/plans/2026-11-04-0215-feat-notch-island-plan.md
  - archive/notch/docs/plans/2026-11-13-feat-island-activity-merge-plan.md
  - archive/notch/docs/plans/2026-11-14-feat-notch-finalize-plan.md
  - archive/notch/docs/plans/2026-11-14-feat-notch-wave2-port-notes.md
  - docs/plans/2026-11-14-feat-dynamic-island-polished-plan.md (PR #73 branch only)
---

# Island

## Goal

One product at the top center of every screen: a Dynamic Island pill that shows what is
happening now, opens when the pointer rests on it, and closes when the pointer leaves.
It replaces two archived products: the tabbed notch (`io.github.duketopceo.notch`) and
the `island-v02` prototype (both in [`archive/`](../../archive/README.md)).

**Built fresh.** The archive is a feature reference, not code to copy. Every feature
below is re-implemented against this plan's contracts. Where an archived module had
good pure logic (geometry tables, priority rules), re-derive it with tests here rather
than moving the file.

## Decisions

| Decision | Choice | Why / rejected |
|---|---|---|
| Plugin id | `io.github.duketopceo.island` (new) | A new id keeps the archived notch's `shell.json` entry and settings from leaking into the new product. Rejected: reusing `.notch` |
| Compact look | Floating pill centered on the camera (virtual pill on external and notchless screens) | From the prototype and notch v0.4+. Rejected: cutout-fill square notch |
| Expanded look | Activity-first card with a short page row. Not a 15-tab dashboard | The notch's tab strip was the clutter. See "Clutter budget" |
| Open/close | Hover opens after a short dwell; leave closes after a grace delay; no click-to-pin trap | See "Hover contract". This was the main failure of the old one |
| Bar | The island never edits `shell.json` `bar.layout` | The notch's `notch-slim-bar` removed widgets from the bar, and uninstalling the notch left them gone (2026-11-14) |
| Notifications / OSD | Stock Omarchy stays the owner by default; the island hosting them is an explicit opt-in | Only one `org.freedesktop.Notifications` owner can exist |
| Integrations | Each one is detected at runtime; missing tools hide the feature, never error | Public plugin: must work on a clean Omarchy box |

## Hover contract (open on hover, close on leave)

### What went wrong before

From the archived code and READMEs (the old sessions record the design, not a bug log,
so these are the failure modes that design allows):

1. **The hover target moved.** A `HoverHandler` sat on the island rectangle, and the
   window's input mask followed that rectangle while it animated. During the open and
   close morph the pointer could fall outside the input region, which produced spurious
   leave and enter events: flicker, half-open states, and panels that closed under the
   pointer.
2. **Any click pinned it open.** A tap on the island set `pinned`, and a pinned island
   ignored the pointer leaving. A user who clicked once got a panel that stayed open
   until they found Esc or an outside click.
3. **Closing depended on a screen-wide catcher.** Click-outside used a transparent
   full-screen layer (later a Hyprland focus grab). The catcher could swallow a click
   meant for an app.
4. **Child controls competed for the pointer.** Tab content with its own mouse areas,
   scroll views and loaders sat inside the hover target; the timing between child
   handlers and the parent's leave was never tested live.

### The contract

| Rule | Value |
|---|---|
| Open | Pointer rests inside the **hot zone** for `openDelay` (default 140 ms, setting 0–600). Moving out before then cancels |
| Close | Pointer outside the hot zone for `closeDelay` (default 450 ms, setting 150–1500). Re-entering within the delay cancels the close |
| Hot zone | A fixed rectangle per state, **not the animating shape**: compact = the pill plus 6 px slop; expanded = the expanded card's final size plus 12 px slop. While a morph runs, the hot zone and input mask are the **larger** of the start and end sizes, so the pointer never falls out mid-animation |
| Click on the compact pill | Opens immediately (skips `openDelay`). Does **not** pin |
| Pin | Only an explicit pin control in the expanded card pins. Pinned shows a visible pin state; leaving does not close; Esc or the pin control unpins and closes |
| Hold-open | Never close while: a slider or scrub is being dragged, a text field has focus, or a context menu from the island is open. The close timer starts when that ends, if the pointer is outside |
| Keyboard | `qs ipc call island toggle` (bindable in Hyprland), Esc closes, Tab moves through controls. Keyboard focus is `OnDemand` only while expanded |
| Fullscreen | Idle island steps aside under real Hyprland fullscreen (mode bit 2); never opens on hover while a fullscreen app is focused |
| No catcher | No full-screen layer. Click-outside closes only via the leave timer (the pointer is already outside) or a focus grab active **only while pinned** |
| Reduced motion | Morph snaps; timings unchanged |

### How it is built

- One pure state machine, `Hover.js`, with no Qt types: states `closed → arming → open
  → leaving → closed`, plus `pinned` and `held` flags. Events: `enter`, `leave`,
  `timer`, `click`, `pin`, `unpin`, `escape`, `holdStart`, `holdEnd`, `fullscreen`.
  It returns `{ state, timer }` the way the archived `Expand.js` did, but with
  pin and hold as first-class inputs.
- Hover is read from one passive `HoverHandler` on a **non-animating** `Item` sized to
  the hot zone. The visual pill animates inside it. The window `mask` binds to the hot
  zone item, never to the visual.
- Unit tests drive the state machine (node), covering: enter/leave under the delays,
  re-enter cancels close, click opens without pin, pin survives leave, hold blocks
  close then releases, Esc from every state, fullscreen forces closed.
- A live check script (`bin/island-hover-check`) uses `hyprctl dispatch movecursor` to
  walk the pointer in, across the morph, onto a child control, and out, and asserts the
  final state from `qs ipc call island state`. It runs in CI-less live verification
  only (needs a session).

## Clutter budget

The notch showed too much at once: a 15-tab strip, a Home tab with weather, media,
quotes, the active app, a calendar, counters and status dots, and ears that rotated
weather and stocks. The Island has hard limits:

| Surface | Limit |
|---|---|
| Left ear | Time (always) |
| Right ear | One thing: the top live activity, else the date. Idle rotation (weather, a quote) is opt-in and off by default |
| Live activities in compact | At most 2 (a second appears only as an icon) |
| Expanded card | The top activity's controls, then up to 2 more activity rows |
| Page row | At most 5 pages visible: **Now** plus the user's top 4 enabled pages. The rest sit behind one "More" chip |
| Any page | One screen, no scrolling for the default content; one accent colour |

Pages appear only when their integration is enabled and detected, so a clean install
shows Now, Media, System and Settings.

## Features to build

Status column: what the archived notch had, for reference only. Phase is when the
Island builds it.

### Shell

| Feature | Notes | Notch had | Phase |
|---|---|---|---|
| Pill geometry | Camera-centred on MacBook cutouts (`/usr/share/omarchy-platform/display-cutouts.json` + `/proc/device-tree/compatible` model table), virtual pill elsewhere; one per screen via `Variants` | yes | P1 |
| Hover contract | Everything in the section above | partial | P1 |
| Clock and date ears | 12/24 h; date in the right ear when idle | yes | P1 |
| Theme | `Commons.Color` / `Commons.Style`, Omarchy theme colours, reduced motion | yes | P1 |
| Settings page | Stored in this plugin's `shell.json` entry; every integration toggle, both delays, page order | yes | P1 |
| Capability probe | One `bin/island-probe` run at load: which integrations exist on this host (existence checks only, no network) | yes | P1 |
| IPC | `toggle`, `open <page>`, `close`, `state` | partial | P1 |
| Fullscreen step-aside | Hyprland fullscreen mode bit 2 | v0.5.0 | P1 |
| Multi-monitor | Independent state per screen | yes | P1 |

### Live activities (compact ear + top of expanded card)

| Activity | Source | Expanded controls | Priority | Notch had | Phase |
|---|---|---|---|---|---|
| Dictation | `wordink` CLI state | Stop | 90 | yes | P2 |
| Media | MPRIS (`Quickshell.Services.Mpris`) | Art, title/artist, scrub, prev/play/next | 50 | yes | P2 |
| Timer | Island's own timer | Pause, +1 min, cancel | 70 | yes | P2 |
| Charging | `/sys/class/power_supply` | Percent, time to full | 30 (brief) | yes | P2 |
| Volume / brightness HUD | PipeWire / backlight; **opt-in**, replaces `omarchy.osd` only when the user disables it | Level bar | 80 (brief) | yes | P2 |
| Agent needs attention | herdr (`herdr-app`) | Open herdr | 60 | yes | P4 |
| New message | Blip (`nixfred.blip`) | Open Blip, preview line | 40 | yes | P4 |
| Screenshot captured | snapdex (`snapdex-ctl`) | Open, copy | 35 (brief) | yes | P4 |
| Dayflow paused | `dayflow status --json` | Resume | 20 | yes | P4 |
| Notifications | Opt-in host; requires `omarchy.notifications` in `disabledPlugins` | Card with actions | 85 | v0.5.0 (partial) | P5 |

One activity list with `{ id, active, priority, text, glyph }` and a tie rule; each
integration is a small `Scope` exposing `active` and `text` (the archived activity
contract was sound; rebuild it with tests).

### Pages (expanded card)

| Page | Content | Source | Default | Notch had | Phase |
|---|---|---|---|---|---|
| Now | All live activities with their controls; if none, time, date, weather and next calendar event | the above | on | Home (cluttered) | P3 |
| Media | Full player, source switcher | MPRIS | on | yes | P3 |
| Network | Tailscale and NordVPN status and connect/disconnect | `/usr/bin/tailscale`, `/usr/bin/nordvpn` | when detected | yes | P3 |
| System | CPU/memory, temperatures, battery, power profile, fan mode | sysfs, `powerprofilesctl`, `lukedaduke.fan` helper | on (fan when detected) | System + Power tabs | P3 |
| Weather | Current and today, pixel icons | Open-Meteo for Omarchy's weather location, cached at most every 15 min | on | yes | P3 |
| Stocks | Watchlist with sparkline | Omarchy finance watchlist; Yahoo public endpoints | off | yes | P3 |
| Messages | Recent threads | Blip | when detected | yes | P4 |
| Agents | herdr sessions needing input | herdr | when detected | yes | P4 |
| Shots | Inbox count, recent captures | snapdex | when detected | yes | P4 |
| Dayflow | Recording state, today's timeline, focus share | `dayflow` CLI, polled only while visible | off | yes | P4 |
| AI usage | Provider usage | `akitaonrails.ai-usagebar` data | off | yes | P4 |
| Clipboard | Recent entries | `cliphist` | when detected | yes | P4 |
| Settings | All toggles, delays, page order | — | on | yes | P1 |

Dropped from the notch: the Plugins hub tab (the bar's tray already does this), the
`notch-slim-bar` bar editor (see Decisions), and the Wisp status dot (Wisp keeps its own
bar widget).

## Phases

| Phase | Outcome | Done when |
|---|---|---|
| P1 Shell | Pill on every screen, hover contract, clock/date, settings, probe, IPC, fullscreen step-aside | State machine tests pass; `island-hover-check` passes live on eDP-1 and the external; no flicker across the morph |
| P2 Core activities | Dictation, media, timer, charging, opt-in HUD | Each activity tested via its pure logic; live check with music playing and a dictation |
| P3 Core pages | Now, Media, Network, System, Weather, Stocks within the clutter budget | Clean install shows ≤5 page chips; each page fits without scrolling |
| P4 Personal integrations | Messages, Agents, Shots, Dayflow, AI usage, Clipboard; their activities | Each hidden when its tool is missing; each live-checked on omarchy-max |
| P5 Notifications + publish | Opt-in notification host; publish to its own repo via `scripts/publish.sh` | Default install never claims D-Bus; `scripts/check-release-readiness.py` exit 0 |

Each phase is one PR off `main`.

## Verification

- `python -m pytest tests/ -q` (new `tests/test_island_*.py`), `python3 scripts/validate-manifests.py`, `python3 scripts/check-qml-syntax.py`.
- Live, per phase: install with `scripts/install.sh --link` from the phase worktree, enable `io.github.duketopceo.island`, run `bin/island-hover-check`, look at both screens in light and dark themes.
- Before calling any phase done: the hover contract table is re-read and every row checked by hand once.

## Out of scope

- Editing the Omarchy bar, lock screen or `/usr/share/omarchy/`.
- macOS or non-Hyprland compositors.
- Restoring the archived notch's settings into the new plugin.
