# Design: Power

Direction: **Pilot Light**, the shared Omarchy-plugin family direction. The tokens, contrast audit,
motion rules and decision ledger live in one place:
[omarchy-plugins/DESIGN.md](https://github.com/duketopceo/omarchy-plugins/blob/main/DESIGN.md). This file only records what is specific to Power.

Status: proposal (2026-10-11).

## Mark

A battery cell outline whose charge fill is the single accent element; the fill is what the bar glyph animates. Files: `assets/brand/logo.svg`, `logo-dark.svg`, `wordmark.svg`, `wordmark-dark.svg`; construction
in `assets/brand/README.md`.

## Surfaces

| Surface | Notes |
|---|---|
| Bar widget | Battery glyph in `foreground`, fill in `Color.accent` while charging, `Color.urgent` plus a word when low. Optional percentage (`showPercentage` setting). |
| Dropdown panel (`Panel.qml`, 1131 lines) | Hero status line, ASCII charge graph, watts graph, top consumers, power profile list, battery health gauge. |
| README / marketplace | Wordmark plus a real screenshot (TODO: capture on a running shell; this pass could not reload the shell). |

## Specifics

- Text in the panel was set with `opacity` 0.4 to 0.6 on `foreground`. Opacity on text is a contrast hazard because it blends with whatever is behind; 0.4 gives under 2:1 on several themes. Rule: Text is `foreground` at 0.85 or higher.
- The ASCII graph is a deliberate texture (terminal feel). Keep it; its colour uses `Style.selectedFillFor`, which follows the theme.
- Empty state (no battery, e.g. desktop): the panel already hides battery sections via `batteryPresent`; keep that as the empty state.

## Fixes applied in this pass (ui commits)

- `ui: power secondary text to 0.85 opacity` replaces seven Text opacities (0.4, 0.45, 0.6, 0.7) in `Panel.qml` lines 766, 843, 885, 928, 1036, 1082, 1120 with 0.85. Behaviour unchanged. Not captured visually: the shell cannot be reloaded from this task.
