# CopyQ Clipboard

Omarchy-native clipboard overlay backed by stock CopyQ. History and MCP stay in
CopyQ; this plugin is the picker surface and follows the active Omarchy theme
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
omarchy-shell shell hide lukedaduke.copyq
```

Typical Hyprland chord (stash-canonical bindings):

```text
SUPER + CTRL + V  →  omarchy-shell shell summon lukedaduke.copyq
```

| Key | Action |
|---|---|
| Type | Filter loaded text rows |
| `↑` / `↓` or `Ctrl+J` / `Ctrl+K` | Move selection |
| `Enter` | Select row in CopyQ and attempt paste |
| `Shift+Enter` | Select onto clipboard only (no paste) |
| `Ctrl+R` | Reload history |
| `Esc` / click scrim | Dismiss |

## Notes

- Text rows only in v0.1 (image / binary previews deferred).
- Paste is best-effort: some surfaces ignore `copyq paste`; the row is still
  selected onto the clipboard.
- Opening the overlay calls `copyq hide` so the stock Qt window stays closed
  on this chord.

## License

MIT
