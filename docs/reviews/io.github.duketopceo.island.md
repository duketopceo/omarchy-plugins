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
