# Design direction: Tape

Status: proposal. Method: the `refero-design` research-first method (reference lock, decision ledger, anti-slop gate). The Refero MCP was not available in this session; references are the Omarchy shell kit itself (`qs.Commons`, `qs.Ui`) and the landscape note, so no external reference was re-fetched.

## 1. Direction

**Name: Tape.** A ticker tape rendered as Omarchy chrome: monospace, flat, square, one accent. Numbers align right; direction is carried by colour plus sign, never colour alone. All colours come from the user's active theme, so a Vantablack and a Flexoki Light user each get their own palette.

Memorable detail: the one accent edge on the selected row; everything else stays on a 20 percent keyline.

## 2. Reference lock

```text
Primary direction: the Omarchy shell kit (Color, Style, KeyboardPanel, BarIconButton).
Preserve: theme colours only; Style.space spacing; bar font family; flat fills, 1px keylines.
Borrow only: terminal-tape conventions (right-aligned figures, signed percent).
Role rules: accent = selection and the "up" chip; urgent = "down" chip and errors only;
  muted = unavailable quotes and hints.
Reject: hardcoded hex, gradients, glow, emoji as icons, drop shadows, row-wide opacity dimming.
```

## 3. Decision ledger

| Decision | Role | Why |
|---|---|---|
| Colours from `Color.*` only | theme owns palette | follows the user's theme; matches `AGENTS.md` convention |
| Text uses `root.bar.fontFamily` | chrome | one monospace face across bar and panel |
| 20 percent keyline, accent edge on selected row | selection | was full-strength border on all rows plus 0.9 opacity; noisy and dimmed text |
| Failed quote chip is muted `--`, not green | state | a failure must not read as "up" (already in code) |
| Status chip says `stale <time>` after a failed refresh | state | the last good snapshot is kept, so say it is old |
| Footer lists `j/k`, Enter, Esc | keyboard | the keyboard path is the main interaction |

## 4. Tokens

No palette of its own: tokens are the theme's. Mapping:

| Use | Token | Notes |
|---|---|---|
| text, keylines | `bar.foreground` (fallback `Color.foreground`) | keyline = foreground at 0.2 alpha (decorative) |
| up chip, selection edge | `Color.accent` | chip fill = accent at 0.22 alpha, text = accent |
| down chip, error line | `Color.urgent` | |
| hints, unavailable | `Color.muted` | |
| panel ground | `Color.popups.background` | |

Contrast: the shell's theme owner is responsible for text-on-ground; what this repo adds is chip text (accent or urgent over its own 0.22 alpha tint of the same colour). I did not compute ratios for arbitrary themes. Known risk: on light themes with a pale accent the chip text can fall under 4.5:1; the sign (`+`/`-`) carries the meaning either way. Static brand colours are in `assets/brand/README.md`.

Type: `Style.font.bodySmall` throughout, bold for symbol, price and change; no italics.

## 5. Icon and glyph style

Bar icon is the shell's Nerd Font glyph (`text: "󰠘"` in `BarIconButton`). The brand mark is a stepped price line ending in a square accent block, 64 px grid, square caps, no rounded joins.

## 6. Motion

None added. The panel has no animation; keep it that way (a ticker that moves is noise). Fetch state is the `syncing` chip.

## 7. Surfaces

| Surface | File | Note |
|---|---|---|
| Bar icon with tooltip | `Panel.qml` `BarIconButton` | left click opens, right click opens TradingView gold |
| Dropdown (2-column grid, 28 px rows) | `Panel.qml` `KeyboardPanel` | `j`/`k`, Enter, Esc |
| README, listing image | `README.md`, `preview.png` | `preview.png` is misleading, roadmap U1 |

## 8. Anti-slop gate

No default indigo, no gradient, no glass: pass. Colour is never the only carrier of direction: pass (signed percent). Generic "dashboard card" look: avoided, rows are a table.
