# Design: Resource & Fan

Direction: **Pilot Light**, the shared Omarchy-plugin family direction. The tokens, contrast audit,
motion rules and decision ledger live in one place:
[omarchy-plugins/DESIGN.md](https://github.com/duketopceo/omarchy-plugins/blob/main/DESIGN.md). This file only records what is specific to Resource & Fan.

Status: proposal (2026-10-11).

## Mark

A three-blade rotor in a ring; the hub is the accent element (the live fan). Files: `assets/brand/logo.svg`, `logo-dark.svg`, `wordmark.svg`, `wordmark-dark.svg`; construction
in `assets/brand/README.md`.

## Surfaces

| Surface | Notes |
|---|---|
| Bar widget | Compact RAM, CPU, temperature readout in `foreground`; `urgent` only above a threshold, with the number visible. |
| Dropdown panel (`Panel.qml`, 2176 lines) | Sections: RAM, CPU, GPU, thermals, fan mode, process list with `j`/`k` and kill, find with `/`. Open PR #28 (`feat/fan-polish`, draft) reworks it into cards. |
| README / marketplace | Wordmark plus a real screenshot (TODO). |

## Specifics

- `Color.muted` fed `root.muted`, which about 30 Text items use. Bundled-theme contrast for `muted` is under 4.5:1 on 20 of 22 themes (DESIGN.md D1). `muted` now derives from `foreground` at 0.85.
- PR #28 moves the panel to GNOME-style cards. This direction agrees with cards but requires the corner radius to come from `Style.cornerRadius` (D5), so a square theme stays square. Rebase this branch's `muted` change over #28 if it lands first; the change is two lines.
- Kill is a destructive action: keep `alert` plus the word "kill" and the exact process name in the confirmation, never colour alone.
- The helper-missing state ("install/update the omarchy-fan-helper package") is the empty state; keep it explicit and copyable.

## Fixes applied in this pass (ui commits)

- `ui: fan muted text derives from foreground (0.85)`: one property in `Panel.qml` (`readonly property color muted`) now returns `Util.alpha(Color.foreground, 0.85)` instead of `Color.muted`, which lifts about 30 labels to AA. Nothing else changed. Not captured visually: shell cannot be reloaded from this task.
