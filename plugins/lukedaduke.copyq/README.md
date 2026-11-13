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
| Click row | Paste that item (old keys included) |
| `↑` / `↓` or `Ctrl+J` / `Ctrl+K` | Move selection |
| `Page Up` / `Page Down` / `Home` / `End` | Jump in list |
| `Enter` | Select in CopyQ and attempt paste |
| `Shift+Enter` | Select onto clipboard only |
| `Delete` | Remove selected row |
| `Ctrl+P` / right-click | Pin clipboard row, or unpin if already on `Pins` |
| `r` / `Ctrl+R` | Reload history (`r` when search is empty; `Ctrl+R` always) |
| `Esc` / click scrim | Dismiss |

## Notes

- Pins appear above clipboard history. Right-click / `Ctrl+P` on a pin removes it.
- **Hot keys (~30 min):** clips that look like API keys (`sk-…`, `sk-or-v1-…`, `sk-ant-…`, `gh*_…`, `github_pat_…`, Slack `xox…`, etc.) are harvested into an encrypted Fernet vault under `$XDG_RUNTIME_DIR/lukedaduke.copyq/` (0600 key + ciphertext). The overlay shows a masked `⏱` row at the top; Enter decrypts and pastes. Delete drops the vault entry. Expires after ~30 minutes or reboot (runtime dir). Plaintext key rows are hidden from the main history list while vaulted.
- Image rows show a thumbnail preview written under `$XDG_RUNTIME_DIR/lukedaduke.copyq/`.
- Paste is best-effort: some surfaces ignore `copyq paste`; the row is still selected onto the clipboard.
- Opening the overlay calls `copyq hide` so the stock Qt window stays closed on these chords.
- History load uses one CopyQ `eval` dump (not one process per row).
- Requires Python `cryptography` (Fernet) for the hot-key vault.
- Not in scope: Clipboard Plus color tools, Kisaku annotate, draft/actions menu.

## License

MIT
