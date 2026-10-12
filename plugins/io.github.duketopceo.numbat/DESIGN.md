# Design: Numbat

Direction: **Pilot Light**, the shared Omarchy-plugin family direction. The tokens, contrast audit,
motion rules and decision ledger live in one place:
[omarchy-plugins/DESIGN.md](https://github.com/duketopceo/omarchy-plugins/blob/main/DESIGN.md). This file only records what is specific to Numbat.

Status: proposal (2026-10-11).

## Mark

Radar rings with a sweep and one accent blip; the blip is a finding. Files: `assets/brand/logo.svg`, `logo-dark.svg`, `wordmark.svg`, `wordmark-dark.svg`; construction
in `assets/brand/README.md`.

## Surfaces

| Surface | Notes |
|---|---|
| Bar widget | Radar glyph; urgent tint when findings landed in the last 24 h; unseen-count badge. |
| Dropdown panel (`Panel.qml`, 1203 lines) | Findings feed with severity chips, agent chips, Log tab (STREAMED or SCANNED), Jev tab. |
| Toast service (`Service.qml`, 656 lines) | Severity-tinted popups, max 3, gated by `toastMinSeverity`, cooled down per rule and agent. |
| Setup pane | Shown when numbat or hooks are missing. |

## Specifics

- Severity is the one place the family uses `alert`. Rule: severity chips carry a word (info, low, medium, high, critical) and the colour is secondary, because `urgent` fails AA on 7 bundled themes.
- `dim` was `Qt.darker(foreground, 1.5)`, about two thirds foreground luminance, which falls below AA on light themes. It is now `foreground` at 0.85.
- Toasts must stay calm: critical stays until clicked, everything else fades; do-not-disturb suppresses. This is design, not just policy; do not add sound or motion.
- The setup pane is the empty state and already says what to run.

## Fixes applied in this pass (ui commits)

- `ui: numbat dim text derives from foreground (0.85)`: one property (`dim`) in `Panel.qml`. Not captured visually: shell cannot be reloaded from this task.
