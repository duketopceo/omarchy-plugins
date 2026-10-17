# Brand assets (proposal)

**Status: proposal.** The owner signs off logos; nothing here ships in the plugin itself.

## Construction

The mark is a price series drawn as a stepped line that climbs to the right and ends in a square accent block, the "last quote" marker. Steps (not a smooth curve) keep it geometric and echo terminal tape.
All geometry sits on a 64 px grid; strokes are 2 or 4 px with square caps and mitred joins, matching the Omarchy shell's flat, square-cornered chrome. The mark is one outlined rounded square (radius 8) plus one accent shape, so it stays readable at 16 px.

## Files

| File | Use |
|---|---|
| `logo.svg` | mark on light backgrounds |
| `logo-dark.svg` | mark on dark backgrounds |
| `wordmark.svg`, `wordmark-dark.svg` | mark plus name; the name is live `<text>` in a monospace stack (not outlined), so it falls back to the reader's monospace font |
| `preview/` | PNG renders, made with `resvg` |

## Colours (static, for README and listing use only)

The running plugin never uses these: it takes `Color.*` from the user's Omarchy theme. GitHub renders `<img>` SVGs without theme access, so the READMEs use fixed light and dark variants.

| Variant | Ink | Accent | Accent contrast on ground |
|---|---|---|---|
| light | `#1c1b18` | `#3f6212` | about 6.5:1 on `#ffffff` |
| dark | `#e8e6df` | `#a3e635` | about 12:1 on `#0d1117` |
