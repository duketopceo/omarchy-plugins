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
