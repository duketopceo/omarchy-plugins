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

Repoint Hyprland F-keys at this binary (see `~/.config/hypr/`) — or keep the
stock `omarchy-capture-screenshot` (Omarchy 4.5 `omasnap`) and set
`OMASNAP_SCREENSHOT_DIR=~/Pictures/Screenshots` to unify the folder. This
plugin only adds the INDEX.log.
