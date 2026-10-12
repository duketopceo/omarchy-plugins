# Roadmap

Program roadmap (2026-10-11): [docs/plans/2026-10-11-001-feat-ticker-program-roadmap-plan.md](docs/plans/2026-10-11-001-feat-ticker-program-roadmap-plan.md). Landscape: [docs/research/2026-10-11-landscape.md](docs/research/2026-10-11-landscape.md).

| Unit | When | Difficulty |
|---|---|---|
| U1 Replace `preview.png` with a real capture | Now | easy |
| U2 Land this PR in the umbrella (`omarchy-plugins`) | Now | medium |
| U3 UI pass (fonts, keylines, stale label, key hints) | Done in this PR | easy |
| U4 Configurable watchlist | Next | medium |
| U5 Market-state labelling | Next | easy to medium |
| U6 Sparkline row | Later | medium |
| U7 Crypto and forex | Later | easy |
| U8 Price-change alerts | Later | hard |
| U9 Decide on a quote source | Later | medium |

Earlier notes follow.

---

# Roadmap

## Current status

Installable and validated. Not yet on the Omarchy marketplace.

## Launch checklist

- [ ] Add a clean `preview.png` of the bar widget and quote panel
- [ ] Submit to https://plugins.omarchy.org/publish.html
- [ ] Set GitHub repo topics and social preview
- [ ] Polish the tagline / one-liner
- [ ] Add a configurable watchlist (settings schema in `manifest.json`)

## Future work

- [ ] Configurable watchlist from the Omarchy settings UI
- [ ] Sparkline / mini chart row in the panel
- [ ] Price-change alerts
- [ ] Crypto and forex symbol support
- [ ] `lukedaduke.standby` integration (already reuses `market_stats.py`)
