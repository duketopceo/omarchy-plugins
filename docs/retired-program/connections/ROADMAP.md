# Roadmap

## Plans

1. [docs/plans/2026-10-11-001-feat-omarchy-connections-program-roadmap-plan.md](docs/plans/2026-10-11-001-feat-omarchy-connections-program-roadmap-plan.md) (2026-10-11): program roadmap. Units land in the `omarchy-plugins` umbrella, then arrive here via `scripts/publish.sh`.

| Horizon | Unit | Difficulty |
|---|---|---|
| Now | U1 Move this docs/brand pass into the `omarchy-plugins` umbrella (subtree publish deletes direct commits) | easy |
| Now | U2 Put radio state in words in the tooltips (`On`/`Off`/`No adapter`) so dimming is not the only signal | easy |
| Now | U3 Fallback icon and a one-line tooltip note if a stock panel path fails to load (today only `console.warn`) | easy |
| Next | U4 Drop the two full embedded stock panels by asking Omarchy for a supported way to open them without loading both | hard |
| Later | U5 Real screenshot and recording on the dual-icon bar; replace `preview.png` mock-up | easy |

Design direction: [DESIGN.md](DESIGN.md). Landscape: [docs/research/2026-10-10-landscape.md](docs/research/2026-10-10-landscape.md).
