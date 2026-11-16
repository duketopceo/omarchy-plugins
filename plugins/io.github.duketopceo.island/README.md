# Island

A pill at the top center of every screen. It shows the time and what is
happening now, opens into a card when the pointer rests on it, and closes on
its own when the pointer leaves. On MacBook panels it sits on the camera
cutout; on other screens it is a virtual pill of the same shape.

P1 is the shell (pill, hover open and close, fixed-size card, fullscreen
step-aside, settings). P2 adds the live activities below. More pages arrive in
later phases.

## Live activities

What is happening now shows in the pill's right ear (glyph and a short form,
such as `0:12` or `46%`); with nothing live the ear shows the date. A second
live activity shows only as an icon at the ear's outer edge. On the card's Now
page the top activity gets its controls and up to two more activities get a
row each. While the card is open nothing moves under the pointer: a new
activity takes a free row, never the top.

| Activity | Source | Card controls | Priority |
|---|---|---|---|
| Dictation | the local `wordink` CLI | Stop (transcribes and pastes, like the shortcut) | 90 |
| Volume and brightness (opt-in) | PipeWire default sink, internal backlight | level bar, about 1.6 s | 80 |
| Timer | the Island's own | pause or resume, +1 min, cancel | 70 |
| Media | MPRIS | art, title and artist, scrub, previous, play or pause, next | 50 |
| Charging | `/sys/class/power_supply` | percent and time to full, about 6 s | 30 |

- Media stays for 10 minutes after a player pauses. Album art shows only from
  local `file:` or `data:` URLs; players that publish `https://` art (Spotify,
  browsers) show a music glyph instead, because loading it would be network
  egress.
- The charging notice shows when the battery starts charging. With a charge
  limit, plugging in at or above the limit reports "Not charging", so no
  notice shows.
- A missing tool hides its activity and shows no error.

### Timer

Start it by IPC or from a keybinding you add yourself:

```bash
qs -p /usr/share/omarchy/shell ipc call island timer 5m   # also 90s, 1h30m, or 10 (minutes); up to 24 h
```

For example, in your own `~/.config/hypr/bindings.lua` (the Island never edits
it):

```lua
o.bind("SUPER + ALT + T", "Island timer 5 min", "/usr/bin/qs -p /usr/share/omarchy/shell ipc call island timer 5m")
```

When it reaches zero the ear shows `Done` for 8 s and one desktop notification
is sent through Omarchy's notification service (when `notify-send` exists). A
timer lives in memory: restarting the shell drops it.

### Volume and brightness HUD

Off unless you turn off Omarchy's own OSD; the Island never does that for you:

```bash
omarchy-plugin-disable omarchy.osd
```

Disabling `omarchy.osd` also drops its microphone-mute, keyboard-brightness
and media popups; the Island shows only output volume, mute and the internal
backlight. `omarchy-plugin-enable omarchy.osd` brings Omarchy's OSD back and
the Island's HUD stops. The HUD only reads; it never changes either level.

## Install

```bash
./scripts/install.sh --link
omarchy plugin enable io.github.duketopceo.island
```

## Settings

Settings live in this plugin's own entry in `shell.json` (`plugins[]`); the
Island writes nothing else there.

| Key | Default | Range | Meaning |
|---|---|---|---|
| `openDelay` | 140 | 0-600 ms | pointer rest time before the card opens |
| `closeDelay` | 450 | 150-1500 ms | time outside the hot zone before the card closes |
| `cameraWidth` | 0 | 0-4000 px | logical camera width override, 0 = auto |
| `dictation` | true | true/false | show the WordInk dictation activity |
| `media` | true | true/false | show the MPRIS media activity |
| `charging` | true | true/false | show the charging notice |
| `hud` | true | true/false | show the volume and brightness level once `omarchy.osd` is disabled |

The Settings page in the card edits all of these.

## The bar clock

The pill covers the center of the bar, where the stock clock sits. To hide the
clock, run this yourself:

```bash
omarchy plugin disable omarchy.clock
```

The Island never runs it and never edits the bar layout.

## Probe

`bin/island-probe` prints one JSON object (platform, which optional tools
exist, display cutouts, device model, battery and backlight names). It checks
existence only and makes no network calls.

## IPC

One target, `island`. Calls act on the screen under the pointer (read once
from `hyprctl cursorpos -j`; the focused monitor only when that fails), except
`close` and `state`, which cover every screen.

```bash
qs -p /usr/share/omarchy/shell ipc call island toggle
qs -p /usr/share/omarchy/shell ipc call island open settings   # or: now
qs -p /usr/share/omarchy/shell ipc call island focus
qs -p /usr/share/omarchy/shell ipc call island close
qs -p /usr/share/omarchy/shell ipc call island state           # JSON, one object per screen
qs -p /usr/share/omarchy/shell ipc call island timer 5m        # "ok" or "invalid"
qs -p /usr/share/omarchy/shell ipc call island act media toggle
```

`act <id> <action>` does what the matching card control does and returns `ok`
or `unknown`: `dictation stop`; `media toggle|next|previous`;
`timer pause|resume|add|cancel` (`add` is +1 min).

`open`, `toggle` and `focus` give the card keyboard focus. An IPC-opened card
stays until the pointer has entered and left it, or 5 s pass untouched.
`state` reports per screen: `screen`, `state`, `flags`, the hot-zone `rect`
(and `pillRect`, `cardRect`, `origin`, `window`, `pinCenter`, `hidden`), the
`top` and `second` activity ids, the card's `held` order, and `activities`
(every live activity's `id`, `priority`, `text` and `card`).

## Hover check

`bin/island-hover-check` is a live check, not part of CI. It moves the real
pointer with `hyprctl dispatch 'hl.dsp.cursor.move({ x = X, y = Y })'`, reads
`island state` after each step, and walks the open, stay-open, click/pin and
Esc cases (AE1, AE2, AE3, AE5) on every screen, with single jumps and with
interpolated steps. It repeats 20 times, exits non-zero on the first mismatch,
and puts the pointer back where it started.

```bash
bin/island-hover-check                                      # 20 runs, all screens
bin/island-hover-check --runs 3 --screens eDP-1 --mode steps
```

Run it on an unlocked desktop with the Island loaded; it refuses to start when
it cannot read the island state or the session reports locked. The click and
Esc cases need `ydotool` (with `ydotoold` running) and `wtype`; without them
those cases are reported as skipped and the exit status is 2 (`--allow-skip`
makes it 0). Pass `--open-delay` and `--close-delay` if you changed the
settings, and `--qs-args` to select a different running shell.
