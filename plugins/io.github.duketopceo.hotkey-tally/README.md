# Hotkey Tally

A bar widget that answers "which of my keybindings do I actually use?"

Counts are aggregate and local: one JSON line per activation in
`~/.local/state/hotkey-tally/uses.jsonl`. Nothing is sent anywhere, and nothing
observes input — the tally only learns about activations that a binding
explicitly reports.

## Why binding counting is opt-in

Hyprland emits no event when a binding is dispatched. Its socket2 event stream
covers windows, workspaces, monitors, submaps and plugins; there is no `bind`
event, and the compositor offers no dispatch counter.

On this Omarchy build there is a second obstacle: `hyprctl binds -j` reports
**every** bind with `dispatcher: "__lua"` and an opaque internal `arg`, because
binds are declared in Lua. The original command cannot be recovered from that
output, so a binding cannot be wrapped after the fact by a generator.

Counting therefore has to happen where the bind is declared — in your own
`~/.config/hypr/bindings.lua`.

## Wiring a binding

```lua
local tally = dofile(os.getenv("HOME") .. "/.config/hypr/hotkey-tally.lua")

-- counted
tally.bind("SUPER + SHIFT + W", "Omawrite", { launch = "omawrite" })
tally.bind("SUPER + M", "Blip iMessage", "blip-toggle")

-- untouched and uncounted
o.bind("SUPER + D", "Wisp push-to-talk (hold)", { launch = "wisp-trigger start" })
```

`tally.bind` records `(id, key, label, timestamp)`, then runs the same command
`o.bind` would have run. If the recording step fails it is silenced and the
original command still runs — a tally must never break a keybinding.

Binds inherited from `/usr/share/omarchy/` are **not countable**. They are
package-owned and must not be edited, and their commands are not recoverable
from `hyprctl`. To count one, shadow it explicitly:

```lua
hl.unbind("SUPER + SHIFT + N")
tally.bind("SUPER + SHIFT + N", "Editor", "omarchy-launch-editor")
```

## Using it

`SUPER + K` opens the tally in a floating terminal (was the stock Keybindings
menu, which moved to `SUPER + SHIFT + K`).

```
s        toggle sort: a-z  <->  used
/        filter by key or action
r        reload from disk
q / Esc  quit
j / k    scroll one row
```

Rows read `KEY  xCOUNT  AGE  ACTION`, so an unused binding is visible as `x0`.

Everything is counted from wrapped binds only. Until a bind is wrapped it
always shows `x0`, which is also the honest reading: the number is activations
since wrapping, not since the key was created.

## Key names on this MacBook Pro

The F-row is reported by Hyprland as `XF86*` symbols, because `fnmode=1` makes
the bare keys emit media codes and only `Fn+F<n>` emits a true F-key. The fork
maps those back to what is printed on the keyboard:

| Emitted symbol | Shown as | Physical key |
|---|---|---|
| `XF86MonBrightnessDown` | `F1` | brightness down |
| `XF86MonBrightnessUp` | `F2` | brightness up |
| `XF86LaunchA` | `F3` | Mission Control |
| `XF86LaunchB` | `F4` | Spotlight |
| `XF86AudioMicMute` | `F5` | dictation / mic |
| `XF86AudioPrev` | `F7` | previous track |
| `XF86AudioPlay` / `XF86AudioPause` | `F8` | play / pause |
| `XF86AudioNext` | `F9` | next track |
| `XF86AudioMute` | `F10` | mute |
| `XF86AudioLowerVolume` | `F11` | volume down |
| `XF86AudioRaiseVolume` | `F12` | volume up |

F6 (Do Not Disturb) emits nothing on this hardware, so it has no binding.
Symbols with no key on a MacBook Pro — `Eject`, `Calculator`, `Touchpad*`,
`KbdBrightness*`, `KbdLightOnOff` — are labelled `(no key)` rather than being
presented as real buttons. `XF86PowerOff` is `POWER (Touch ID)`.

## Files

| Path | Role |
|---|---|
| `bin/hotkey-tally.py` | `record`, `list`, `prune`, `reset` |
| `hotkey-tally.lua` | `tally.bind` / `tally.wrap` helpers for `bindings.lua` |
| `Panel.qml` | bar glyph (total) + filterable ranked list |
| `tests/` | behaviour tests, run with `uv run --with pytest python -m pytest tests/` |

## CLI

```
hotkey-tally.py record --id ID --key "SUPER + T" --label "Terminal"
hotkey-tally.py list [--json] [--limit N] [--search TEXT]
hotkey-tally.py prune --keep 50000
hotkey-tally.py reset
```

Rows are pruned to the newest 50,000 by `prune`, or on write when
`HOTKEY_TALLY_PRUNE=1`.

## Privacy boundary

- The recorded row schema is fixed to `{id, key, label, ts}`; a test asserts it.
- No text, clipboard content, window titles, or command arguments are stored.
- No network access from any file here.
- A binding you do not wrap is invisible to this plugin.
