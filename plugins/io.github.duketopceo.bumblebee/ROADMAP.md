# Roadmap

## Plans

1. [docs/plans/2026-10-11-001-feat-omarchy-bumblebee-program-roadmap-plan.md](docs/plans/2026-10-11-001-feat-omarchy-bumblebee-program-roadmap-plan.md) (2026-10-11): program roadmap. Units land in the `omarchy-plugins` umbrella, then arrive here via `scripts/publish.sh`.

| Horizon | Unit | Difficulty |
|---|---|---|
| Now | U1 Move this docs/brand pass into the `omarchy-plugins` umbrella so the next `publish.sh` does not delete it | easy |
| Now | U2 Fixture test for `bin/scan_bumblebee.py` and `refresh_catalog.py` (tar traversal, schema reject, partial scan) | medium |
| Now | U3 Add a severity word to the bar tooltip, toast and exposure rows so urgency never relies on colour | easy |
| Next | U4 Verify refreshed advisories: pin a SHA-256 of the release tarball next to the tag `v0.1.2` | medium |
| Next | U5 Split `Panel.qml` (1021 lines) into one file per tab and share `accentFill`/`fgFill` with the other plugins via umbrella `shared/` | medium |
| Later | U6 Real README screenshot and a 10 s recording from a live session | medium |

Design direction: [DESIGN.md](DESIGN.md). Landscape: [docs/research/2026-10-10-landscape.md](docs/research/2026-10-10-landscape.md).
