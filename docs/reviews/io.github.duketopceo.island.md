# Review: io.github.duketopceo.island (omarchy-island)

Reviewed: pending · verdict: PENDING

Initial scorecard for the Island panel plugin. Criteria match the family
scorecard keys; assessment deferred until after the live hover check.

## Scorecard

See docs/SCORECARD.md for semantics.

```scorecard
{
  "plugin": "io.github.duketopceo.island",
  "criteria": {
    "no_open_hm_findings": "pending",
    "plaintext_external_text": "pending",
    "exec_discipline": "pending",
    "envelope": "pending",
    "fixture_tests": "pending",
    "visibility_gating": "pending",
    "stale_backoff": "pending",
    "readme_claims": "pending"
  },
  "manual": {
    "spawn_measurement": {
      "date": null
    },
    "asahi_pass": {
      "date": null
    },
    "x86_64_pass": {
      "date": null
    }
  },
  "notes": "Initial state: not yet assessed against docs/SCORECARD.md."
}
```

## Notes

### U1 live probes

Run 2026-11-15 on omarchy-max, Hyprland 0.57.2, eDP-1 only (3456x2234, scale 2, logical 1728x1117; DP-3 not connected).

| Question | Answer | Branch |
|---|---|---|
| Pointer move command | `hyprctl dispatch 'hl.dsp.cursor.move({ x = X, y = Y })'` moves the pointer (confirmed with `hyprctl cursorpos`); `hyprctl eval` with the same Lua returns `ok` but does not move it | KTD11: use `dispatch` |
| Does the move produce hover enter/leave? | Yes, once unlocked: the probe logged `hovered=true` on entry and `hovered=false` on exit (the first attempt ran on the lock screen and saw nothing) | KTD11 live check is viable |
| Layer Top covered by a fullscreen window | Moot: the island unmaps under real fullscreen (see AE6 below) | KTD6 |
| Leave after the mask shrinks under a still pointer | Yes: shrinking the mask from card to pill with the pointer in the dropped area produced `hovered=false` 2 ms later | KTD3 cursor re-check fallback not needed; removed |
| `HyprlandFocusGrab` clears by itself | No (held 8 s). But while the grab is active Hyprland sends no pointer leave: the pointer moved outside and `hovered` stayed true | KTD5 fallback: `OnDemand` focus without a grab, so a focused card still closes on leave |
| Island vs bar stacking | The bar is a full-screen-sized layer-2 (Top) surface. A probe on Top drew above the bar's icons and took the pointer at the bar center (icon pixels measured pink under the 50% red probe), but only because it mapped after the bar; that order is not guaranteed across shell restarts. Overlay (level 3) sits above the bar by layer | KTD1 fallback: layer Overlay |

### Live verification (P1, eDP-1)

| Check | Result |
|---|---|
| Plugin loads | `omarchy-island` mapped on layer 3 at 744x392; no Island errors in the shell log |
| Pill | Time and short date ears render (screenshot) |
| AE1, AE2 hover open/close | `bin/island-hover-check --runs 20 --mode both`: 20/20 passed, single jumps and interpolated steps |
| AE3 click-open and pin, AE5 Esc with rearm | Not automated: needs `ydotoold` (disabled on this host); manual pass pending |
| AE4 keybinding/IPC open | `qs ipc call island toggle` opened with `summoned` and `focused`; closed by itself after 5 s untouched |
| AE6 fullscreen | Scratch window fullscreen: island hidden and its layer unmapped; restored on exit; maximized does not hide it |
| DP-3 | Not connected during this run |
| Settings save (U7) | Not exercised live (needs a click into the card); manual pass pending |

### Live verification (P2 live activities, eDP-1)

Run 2026-11-15 on omarchy-max, Hyprland 0.57.2, eDP-1 only, screen unlocked. Plan: `docs/plans/2026-11-15-1645-feat-island-live-activities-plan.md`. Actions were driven through `qs ipc call island act ...`, the same path the card's controls take, because no click injector runs on this host.

| Check | Result |
|---|---|
| Plugin loads | No Island warnings in the shell log after the binding-loop and FileView fixes |
| Media (R7) | mpv playing a tagged local file (null audio output): ear shows play glyph + title; card shows art placeholder, title, artist, scrub 0:15 of 10:00, prev/next dimmed (one track); `act media toggle` moved MPRIS PlaybackStatus Playing, Paused, Playing; paused media stayed in the ear |
| Dictation (R6, AE2) | Scratch foot window focused; `wordink dictation start` showed `0:02` in the ear with the media icon at the outer edge (KTD10); `act dictation stop` ended it (WordInk log: `discarded`, nothing was said, nothing pasted); the activity cleared |
| AE1 held order | Card open on media, then a dictation started: media stayed the top block, dictation took a row with its Stop control |
| Timer (R8, AE3) | `timer 2m` showed 1:59; `+1 min` gave 2:59; paused held 2:59 for 2 s; resume, cancel, `timer bogus` returned `invalid`; a 5 s timer showed `Done` then cleared; exactly one `Notify` ("Island", "Timer done") on the session bus |
| Charging (R13) | A real transition into Charging during the run showed `69% · 3h 28m to full` once and expired on its own |
| HUD (R9, AE4) | With `omarchy.osd` enabled a volume change showed nothing; after `omarchy-plugin-disable omarchy.osd` it showed `47%`, and a backlight change showed `26%`; `omarchy-plugin-enable omarchy.osd` restored it; shell.json identical to the pre-run copy, volume and brightness restored |
| Settings page | Opened by `open settings`: both delays and four toggles fit the card without clipping; the OSD hint shows while `omarchy.osd` is enabled |
| Hover regression | `bin/island-hover-check --runs 5 --mode both` with media live: 5/5 (AE1, AE2, jump and steps); pointer restored |
| Not run live | Clicking card controls (Stop, transport, scrub drag, toggles): needs a click injector; manual pass pending. A spoken dictation whose transcript lands in the focused window: needs a person speaking |

Findings fixed during the run:

- WordInk reports `listening` as its ready state after every dictation; only `dictating` is recording. The ear showed "Recording" forever until `Dictation.js` stopped mapping `listening` to recording.
- `FileView.reload()` is asynchronous; reading `text()` right after it returned the previous contents, so the brightness level lagged one change behind. Brightness and charging now read in `onLoaded`.
- `time_to_full_now` refuses reads unless the battery is charging; it is now read only then, which stopped a warning every 5 s.
