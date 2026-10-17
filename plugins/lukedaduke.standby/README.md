<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/wordmark-dark.svg">
    <img src="assets/brand/wordmark.svg" alt="omarchy-standby" height="48">
  </picture>
</p>

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

## What it shows

- Large horizontal clock with AM/PM and date
- Weather from Open-Meteo: condition, temp, high/low, humidity, wind, sunrise, sunset
- Pure black background; content stays extremely dim for OLED/dark rooms

## Notes

- Caffeine mode writes `~/.local/state/omarchy/indicators/stay-awake` so the idle daemon does not lock or blank the display.
- The overlay does not replace `omarchy.idle`, `omarchy.lock`, or the existing screensaver.

## License

MIT

## Status and design

- Roadmap: [ROADMAP.md](ROADMAP.md)
- Design direction (Pilot Light, shared by the Omarchy plugin family): [DESIGN.md](DESIGN.md)
- Landscape research: [docs/research/2026-10-11-landscape.md](docs/research/2026-10-11-landscape.md)
- Authoring catalog and shared rules: https://github.com/duketopceo/omarchy-plugins

## Contributing

This repository is the published mirror of [`duketopceo/omarchy-plugins`](https://github.com/duketopceo/omarchy-plugins) (`plugins/lukedaduke.standby/`). Send changes to the umbrella; a direct commit here is overwritten by the next publish.
