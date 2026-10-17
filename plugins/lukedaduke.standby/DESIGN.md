# Design: Standby

Direction: **Pilot Light**, the shared Omarchy-plugin family direction. The tokens, contrast audit,
motion rules and decision ledger live in one place:
[omarchy-plugins/DESIGN.md](https://github.com/duketopceo/omarchy-plugins/blob/main/DESIGN.md). This file only records what is specific to Standby.

Status: proposal (2026-10-11).

## Mark

A crescent with one accent star dot; night is the product. Files: `assets/brand/logo.svg`, `logo-dark.svg`, `wordmark.svg`, `wordmark-dark.svg`; construction
in `assets/brand/README.md`.

## Surfaces

| Surface | Notes |
|---|---|
| Overlay (`Standby.qml`, 422 lines) | Fullscreen, pure black. Large clock, date, weather (Open-Meteo), sunrise and sunset. Keys: Esc/Q/Space dismiss, R red tint, B brightness, C caffeine. |
| README / marketplace | Wordmark plus a dark-room screenshot in red-tint mode (TODO; shell not reloadable here). |

## Specifics

- **Exception to the family contrast rule.** Standby is used in a dark room next to a bed. The goal is a luminance ceiling: pure black background (OLED pixels off), content opacities 0.45 to 0.8, and a low-brightness mode that drops one element to 0.12. It must never exceed theme `foreground`. Do not "fix" this to AA.
- The red tint (R) is the night-vision mode: it mixes `Color.urgent` at 0.10 into the text colour. Because `urgent` is theme-derived the tint stays on-theme; on themes where `urgent` is very dark (miasma 2.3:1) the tint effect is weak, which is acceptable in a dark room.
- Caffeine state is signalled with `Color.urgent` on its label; add the word ("awake") so colour is not the only carrier.
- Motion: none beyond the clock tick; no animation on an OLED surface to avoid burn-in streaks.

## Fixes applied in this pass (ui commits)

No UI commit in this pass: the intended dimness is the design (see Specifics); changing opacities would be a regression.
