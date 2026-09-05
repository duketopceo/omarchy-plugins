# Standby

An OLED-friendly nightstand overlay for Omarchy — iPhone StandBy-style horizontal display that can be summoned manually without touching the screensaver or lock screen.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-standby
omarchy plugin enable lukedaduke.standby
```

## Use

```bash
omarchy-shell shell summon lukedaduke.standby
omarchy-shell shell hide lukedaduke.standby
```

| Key | Action |
|---|---|
| `Esc` / `Q` / `Space` | Dismiss the overlay |
| `R` | Toggle subtle red tint |
| `B` | Toggle low/high brightness |
| `C` | Caffeine / stay-awake mode |
| `M` | Refresh market data |

## What it shows

- Large horizontal clock with AM/PM and date
- Weather from Open-Meteo: condition, temp, high/low, humidity, wind, sunrise, sunset
- Market rows (reuses `lukedaduke.ticker`'s `market_stats.py` when installed)
- Pure black background; content stays extremely dim for OLED/dark rooms

## Notes

- Caffeine mode writes `~/.local/state/omarchy/indicators/stay-awake` so the idle daemon does not lock or blank the display.
- The overlay does not replace `omarchy.idle`, `omarchy.lock`, or the existing screensaver.

## License

MIT
