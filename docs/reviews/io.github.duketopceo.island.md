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
| Does the move produce hover enter/leave? | Not answered: the session was on the lock screen, so pointer events went to the lock surface and the probe saw none | Pending |
| Layer Top covered by a fullscreen window | Not answered (screen locked) | Pending; KTD6 hides the island under fullscreen either way |
| Leave after the mask shrinks under a still pointer | Not answered (screen locked) | Pending; KTD3 fallback not built yet |
| `HyprlandFocusGrab` clears by itself | Not answered (screen locked) | Pending |
| Island vs bar stacking on layer Top | Partly: `omarchy-bar` is a full-screen-sized layer-2 (Top) surface with an input mask; the probe also mapped on layer 2. Which one draws on top and takes the pointer at the bar's center was not observable (screen locked) | Pending; KTD1 stays Top until this is checked |

Re-run the probes with the screen unlocked before U4–U6 live verification.
