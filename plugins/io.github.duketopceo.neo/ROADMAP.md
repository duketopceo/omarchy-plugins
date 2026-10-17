# Roadmap

## Plans

1. [docs/plans/2026-10-11-001-feat-omarchy-neo-program-roadmap-plan.md](docs/plans/2026-10-11-001-feat-omarchy-neo-program-roadmap-plan.md) (2026-10-11): program roadmap. Units land in the `omarchy-plugins` umbrella, then arrive here via `scripts/publish.sh`.

| Horizon | Unit | Difficulty |
|---|---|---|
| Now | U1 Move this docs/brand pass into the `omarchy-plugins` umbrella | easy |
| Now | U2 Complete the manifest: add the `barWidget` block (displayName, category, defaultSection) and `activation` like the sibling plugins | easy |
| Now | U3 Words with every state: `UP`/`DOWN`/`MCP silent` in the tooltip and glyph state, not tint only | easy |
| Next | U4 Unit test for `bin/probe_neo.py` with faked `systemctl` and a fake MCP server | medium |
| Later | U5 Generalise unit names and ports to one constants block, still no config plumbing | medium |

Design direction: [DESIGN.md](DESIGN.md). Landscape: [docs/research/2026-10-10-landscape.md](docs/research/2026-10-10-landscape.md).
