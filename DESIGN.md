# Design direction: Pilot Light

Shared design direction for the Omarchy plugin family: `omarchy-plugins` (catalog), `omarchy-power`,
`omarchy-fan`, `omarchy-standby`, `omarchy-numbat`. Written once here; each plugin repo's `DESIGN.md`
adds only its own surfaces and exceptions.

**Status: proposal (2026-10-11).** Logos and the name are for the owner to sign off.

## The idea

A plugin is an instrument on someone else's dashboard. It must look like it shipped with the user's
Omarchy theme, not like a guest. So **Pilot Light** has one rule: the plugin carries no palette of
its own. Everything is the user's theme, plus exactly one small lit thing per surface that says
"this is live" (a dot, a fill, a hub). Quiet by default, one signal when something is true.

Why not a branded look: Omarchy ships 22 themes (`/usr/share/omarchy/themes`, light and dark) and
the host resolves colours from the active theme at runtime (`qs.Commons` `Color`, `Style`). A plugin
that hardcodes colour breaks on the next `omarchy theme set`. AGENTS.md already says "Theme with
`qs.Commons` `Color` / `Style` only"; this document says how, and where the host's own roles fall short.

## Reference lock

| # | Reference | What we take | What we reject |
|---|---|---|---|
| R1 | Omarchy's `Color.qml` / `Style.qml` (read-only, `/usr/share/omarchy/shell/Commons`) | The role set: `foreground`, `background`, `accent`, `urgent`, `muted`, `popups.*`, `tooltip.*`; `Style.cornerRadius` (default 0), `Style.space()`, `Style.normalFillFor()` | Nothing; it is the contract |
| R2 | Omarchy theme files (`themes/<name>/colors.toml`) | Measured the 22 bundled themes for contrast (table below) | Assuming the palette is designed for small text |
| R3 | iOS StandBy / Apple Watch complications | One glanceable number per surface, large and quiet | Rounded-everything and fixed brand colours |
| R4 | btop / Waybar modules | Dense, tabular, keyboard-first panels | Raw unstyled text walls |
| R5 | GNOME Mission Center (cited by the fan polish plan, `docs/plans/2026-10-10-001-*`) | Card-per-metric grouping | Hardcoded corner radius (radius must come from `Style.cornerRadius`) |

## Decision ledger

| ID | Decision | Evidence | Alternative rejected |
|---|---|---|---|
| D1 | Never use `Color.muted` for text | Measured: `muted` vs `background` is under 3:1 on 19 of 22 bundled themes and under 4.5:1 on 20 (worst: rose-pine 1.5, matte-black 1.5, everforest 1.6, hackerman 1.6) | Keeping muted for secondary text; fails AA on almost every theme |
| D2 | Secondary text is `foreground` at alpha 0.85 (token `dim`) | Worst bundled theme (rose-pine, light) still reaches 4.66:1 at 0.85; at 0.80 it falls to 4.16 | `Qt.darker(fg, 1.5)` and `opacity: 0.4 to 0.6` on Text, both found in the code and both fail |
| D3 | `foreground` carries all meaning-bearing text | foreground vs background is 6.7:1 or better on all 22 themes | Colour-only status text |
| D4 | `accent` and `urgent` are fills, rules, glyphs and large text, never the only carrier of small text or state | accent under 4.5:1 on 3 themes, urgent under 4.5:1 on 7 (miasma 2.3, solitude 2.8, nord 3.1, kanagawa 3.2) | Red text for errors; pair with a glyph and a word |
| D5 | Radius comes from `Style.cornerRadius`, never a literal | Host default is 0 and themes can set it | Fixed 8px cards (conflicts with themes that choose square) |
| D6 | Marks are 24-grid, 2 px stroke, square caps, miter joins, one accent element | Matches Omarchy's default radius 0; reads at 16 px | Rounded glyph sets, stock icons |

## Contrast audit (22 bundled themes, WCAG 2.1 ratios against theme `background`)

| Role | Worst case | Fails AA 4.5:1 | Use |
|---|---|---|---|
| `foreground` | 6.7 (rose-pine) | 0 themes | All text |
| `foreground` at 0.85 (`dim`) | 4.66 (rose-pine) | 0 themes | Secondary text |
| `accent` | 3.1 (rose-pine) | 3 themes | Fills, rules, glyphs only |
| `urgent` (theme `red`) | 2.3 (miasma) | 7 themes | Fills and glyphs, plus a word |
| `muted` | 1.5 (rose-pine, matte-black) | 20 themes | Borders and dividers only, never text |

Method: `colors.toml` per theme, relative luminance per WCAG 2.1; alpha blends computed against the
theme background (popup backgrounds default to `background`; themes that override `popups.background`
should be spot-checked). Brand-file colours (README only, fixed): ink `#14181b` on white 17.85, accent
`#2f6fed` on white 4.55, dark ink `#e6e8ea` on `#1a1b26` 13.91, dark accent `#7aa2f7` 6.79.

## Tokens (map onto the theme, do not replace it)

| Token | Light and dark | QML | Use |
|---|---|---|---|
| `text` | theme foreground | `bar.foreground` or `Color.foreground` | Primary text, numerals |
| `dim` | foreground, alpha 0.85 | `Util.alpha(Color.foreground, 0.85)` | Labels, units, captions |
| `signal` | theme accent | `Color.accent` | The one lit element: fill, dot, active tab rule |
| `alert` | theme urgent | `Color.urgent` | Threshold crossed; always with a glyph and a word |
| `surface` | theme popup background | `Color.popups.background` | Panel body |
| `hairline` | foreground, alpha 0.10 to 0.40 | `Style.normalBorderFor(...)` | Dividers, borders (this is where `muted`-like weight belongs) |
| `fill-idle/hover/selected` | host state fills | `Style.normalFillFor`, `hoverFillFor`, `selectedFillFor` | Rows and buttons |
| `radius` | host | `Style.cornerRadius` | Cards and chips |
| `space` | host | `Style.space(n)` | All padding and gaps |

Both light and dark come for free because every token resolves through the active theme. There is no
separate dark palette to maintain. Theme swap is live (host reassigns `shellValues`), so bindings must
be property bindings, not one-time reads.

## Type

No fonts shipped; the host font and `Style.font` rule. Numerals that update (temps, RPM, watts,
percent) use the host's tabular figures where the font has them so digits do not jitter. Hierarchy
by size and `dim`, not weight and colour: hero numeral, label in `dim`, unit in `dim` at smaller size.
Panel text sizes stay on the host scale (`Style.font*`); do not set literal pixel sizes.

## Glyph and mark style

24-unit grid, 2 px stroke, square caps, miter joins, no gradients, one accent element per mark
(a dot, a fill or a hub). Marks sit in `assets/brand/` per repo. They are README and marketplace art;
inside the bar the glyph is drawn in `foreground` with the accent element in `Color.accent`, so it
follows the theme. Logo files use fixed ink and accent hex because GitHub cannot read the user's theme.

| Repo | Mark | Accent element |
|---|---|---|
| omarchy-plugins | 2x2 grid of tiles | the one filled tile |
| omarchy-power | battery cell | charge fill |
| omarchy-fan | ring and three-blade rotor | hub |
| omarchy-standby | crescent | star dot |
| omarchy-numbat | radar rings and sweep | blip |

## Sibling plugins

bumblebee, connections, neo, nexus and pplx got their own DESIGN.md in a parallel pass (`plugins/<id>/DESIGN.md`;
nexus: "Schematic, not cockpit"). They already defer to this file and use the same grammar at a 16 px grid
with a 1.5 px stroke; the five marks here use the 24 grid with a 2 px stroke. Same rules, two sizes. Where they
disagree, this file wins. connections is retired (notice-only stub; its mirror PR is not ported because the retirement test requires a stub-only tree).

## Motion

Subtle, theme-neutral, and cheap (the bar is always on screen).
- State changes (colour, fill) ease 160 to 220 ms; the existing `ColorAnimation { duration: 200 }` in power is the house value.
- Panel content never animates continuously. The only perpetual motion allowed is a single slow pulse on the `signal` element while a live process is running, and none when the surface is hidden (`VisibilityGate`).
- Timers under one second must be one-shot or tied to an animation lifetime (`docs/PLUGIN_CONTRACT.md`).
- Respect reduced motion where the host exposes it; otherwise keep motion to opacity and colour, no travel.

## Surfaces across the family

| Surface | Who | Rules |
|---|---|---|
| Bar widget | power, fan, numbat | Glyph plus at most one short value; `foreground`; `signal` or `alert` only when state warrants; must work at the host bar height |
| Dropdown panel | power, fan, numbat | `surface` background, `hairline` dividers, one hero value, `dim` labels, `j`/`k` and Esc keyboard paths, visible focus ring from `Style.focusBorderFor` |
| Overlay | standby | Exception ledger below |
| README and marketplace | all | Logo pair (light and dark via `<picture>`), screenshot captured on a real theme |
| Empty, loading, error | all | Say what is missing and the one command that fixes it; never a blank panel; errors use `alert` plus a word |

## Exceptions

- **Standby** is an OLED nightstand. In a dark room the goal is a luminance ceiling, not a contrast
  floor: content is intentionally dim (element opacities of 0.45 to 0.8) and low-brightness mode drops at least one element to 0.12. It is
  exempt from D2 and must never be brighter than the theme's `foreground`. Its pure-black background
  is deliberate (OLED off pixels). See `omarchy-standby/DESIGN.md`.

## Checking a theme swap

Not automated yet (roadmap `omarchy-plugins` U2). Manual: `omarchy theme set <name>` for one light
theme (`white`, `rose-pine`) and one dark low-contrast theme (`miasma`, `matte-black`), then open each
panel. Do not run this on a machine you cannot reload.
