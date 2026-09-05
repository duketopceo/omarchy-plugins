# lukedaduke.standby

Fullscreen OLED-friendly nightstand overlay for Omarchy — iPhone StandBy-style horizontal display without touching the screensaver or lock screen.

## Shows

- Large clock + AM/PM + date
- Weather: condition, temp, high/low, humidity, wind, sunrise/sunset (Open-Meteo)
- Market watchlist rows (reuses `lukedaduke.ticker`'s `market_stats.py` if installed)

## Use

```bash
omarchy-shell shell summon lukedaduke.standby
omarchy-shell shell hide lukedaduke.standby
```

Keys: `Esc` / `Q` / `Space` dismiss · `R` red tint · `B` brightness · `C` caffeine (toggles `~/.local/state/omarchy/indicators/stay-awake` so the idle daemon won't lock/blank) · `M` refresh markets.

Background is pure black; content renders at ~5% opacity in low-brightness mode for OLED/dark rooms.
