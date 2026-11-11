# Screenshots

Unified screenshot sink for Omarchy. All captures land in:

```
~/Pictures/Screenshots/YYYY-MM-DD/shot-YYYYMMDD-HHMMSS.png
```

with one line appended to `~/Pictures/Screenshots/INDEX.md` per capture.

## Use

```bash
bin/screenshot-sink full    # fullscreen (grim)
bin/screenshot-sink area    # region (grim + slurp)
bin/screenshot-sink open    # open today's folder
bin/screenshot-sink log "note"  # manual INDEX.md log entry
```

Repoint Hyprland F10/F11/F12 binds at this binary (see `~/.config/hypr/`).
