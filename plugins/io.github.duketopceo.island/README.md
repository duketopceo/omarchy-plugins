# Island

A pill at the top center of every screen. It shows the time and what is
happening now, opens into a card when the pointer rests on it, and closes on
its own when the pointer leaves. On MacBook panels it sits on the camera
cutout; on other screens it is a virtual pill of the same shape.

This is P1 (the shell: pill, hover open and close, fixed-size card, fullscreen
step-aside, settings). Further activities and pages arrive in later phases.

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

## The bar clock

The pill covers the center of the bar, where the stock clock sits. To hide the
clock, run this yourself:

```bash
omarchy plugin disable omarchy.clock
```

The Island never runs it and never edits the bar layout.

## Probe

`bin/island-probe` prints one JSON object (platform, which optional tools
exist, display cutouts, device model). It checks existence only and makes no
network calls.

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
```

`open`, `toggle` and `focus` give the card keyboard focus. An IPC-opened card
stays until the pointer has entered and left it, or 5 s pass untouched.
`state` reports per screen: `screen`, `state`, `flags`, the hot-zone `rect`
(and `pillRect`, `cardRect`, `origin`, `window`, `pinCenter`, `hidden`).

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
