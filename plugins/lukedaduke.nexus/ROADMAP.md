# Roadmap

## Plans

1. [docs/plans/2026-10-11-001-feat-omarchy-nexus-program-roadmap-plan.md](docs/plans/2026-10-11-001-feat-omarchy-nexus-program-roadmap-plan.md) (2026-10-11): program roadmap. Units land in the `omarchy-plugins` umbrella, then arrive here via `scripts/publish.sh`.

| Horizon | Unit | Difficulty |
|---|---|---|
| Now | U1 Move this docs/brand pass into the `omarchy-plugins` umbrella | easy |
| Now | U2 Make the pulse conditional: run `animPulse` only while a probe is in flight, not the whole time the panel is open | easy |
| Now | U3 Check the selected-tab contrast: `Color.background` text on an `accent` fill across themes | easy |
| Next | U4 Keyboard tab switching like `pplx` (`onTabRequested`) | medium |
| Next | U5 Replace the `preview.png` mock-up with a real capture; fix `AGENTS.md` (says ~380 lines, file is 583) | easy |
| Later | U6 Fixture test for `bin/probe_nexus.py` (missing `bluetoothctl`, missing `/sys/bus/usb`) | medium |

Design direction: [DESIGN.md](DESIGN.md). Landscape: [docs/research/2026-10-10-landscape.md](docs/research/2026-10-10-landscape.md).
