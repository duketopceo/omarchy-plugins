# CopyQ Clipboard

Paste-like Omarchy clipboard overlay backed by stock CopyQ. History and MCP stay
in CopyQ; this plugin is the picker surface and follows the active Omarchy theme
via `qs.Commons` Color / Style.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-copyq
omarchy plugin enable lukedaduke.copyq
```

Requires `/usr/bin/copyq` running as a daemon (`copyq --start-server`).

## Use

```bash
omarchy-shell shell summon lukedaduke.copyq
omarchy-shell shell summon lukedaduke.copyq '{"mode":"cursor"}'
omarchy-shell shell hide lukedaduke.copyq
```

Typical Hyprland chords (stash-canonical bindings):

```text
SUPER + CTRL + V   →  centered history (summon)
SUPER + SHIFT + V  →  at-cursor menu (summon mode=cursor)
SUPER + ALT + V    →  silent copyq next (no UI)
```

| Key | Action |
|---|---|
| Type | Filter loaded rows (text + images + pins) |
| `↑` / `↓` or `Ctrl+J` / `Ctrl+K` | Move selection |
| `Page Up` / `Page Down` / `Home` / `End` | Jump in list |
| `Enter` | Select in CopyQ and attempt paste |
| `Shift+Enter` | Select onto clipboard only |
| `Delete` | Remove selected row |
| `Ctrl+P` / right-click | Pin clipboard row into CopyQ `Pins` tab |
| `Ctrl+R` | Reload history |
| `Esc` / click scrim | Dismiss |

## Notes

- Pins appear above clipboard history.
- Image rows show a thumbnail preview written under `$XDG_RUNTIME_DIR/lukedaduke.copyq/`.
- History loads via a single `copyq eval` (in-process), not per-row CLI reads.
- Paste injects the universal chord with `wtype` — `Ctrl+Shift+V` into
  terminals, `Ctrl+V` elsewhere — matching Omarchy's SUPER+V semantics;
  `copyq paste` cannot inject keys on Wayland. If `wtype` is missing it falls
  back to `copyq paste`, which some surfaces ignore; the row is still selected
  onto the clipboard either way.
- Opening the overlay calls `copyq hide` so the stock Qt window stays closed on these chords.
- Not in scope: Clipboard Plus color tools, Tensaku annotate, draft/actions menu.

## License

MIT
