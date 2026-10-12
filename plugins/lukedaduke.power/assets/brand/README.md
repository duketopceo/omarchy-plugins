# Brand: omarchy-power (proposal)

Hand-written SVG, no raster, no AI generation, no stock icons. The owner signs off logos; treat this
as a proposal. Family rules are in [omarchy-plugins/DESIGN.md](https://github.com/duketopceo/omarchy-plugins/blob/main/DESIGN.md).

## Construction

24 x 24 grid, 2 px stroke, square caps, miter joins. A 15 x 10 outline body, a 3 x 4 terminal, and a 6 x 4 charge fill in the accent. One accent element only.

## Files

| File | Use |
|---|---|
| `logo.svg` | Mark on light backgrounds (ink `#14181b`, accent `#2f6fed`) |
| `logo-dark.svg` | Mark on dark backgrounds (ink `#e6e8ea`, accent `#7aa2f7`) |
| `wordmark.svg`, `wordmark-dark.svg` | Mark plus `omarchy-power` set in JetBrains Mono (OFL), text converted to paths |
| `logo-preview.png` | Preview of both, at 128, 16 and 32 px sizes |

Fixed hex is used here only because GitHub cannot read the user's Omarchy theme. In the bar the same
glyph is drawn with `Color.foreground` and `Color.accent` so it follows the theme.

README usage:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/brand/wordmark-dark.svg">
  <img src="assets/brand/wordmark.svg" alt="omarchy-power" height="48">
</picture>
```
