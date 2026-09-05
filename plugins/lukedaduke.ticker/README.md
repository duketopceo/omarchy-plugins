# Market Watchlist

A lightweight Omarchy bar widget for tracking a fixed watchlist of quotes: gold, tech, nuclear, energy, and rates.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-ticker
omarchy plugin enable lukedaduke.ticker
```

## Features

- Yahoo chart endpoints for live(ish) quotes
- Clean panel with `j`/`k` navigation
- Enter opens the selected symbol on TradingView
- Keeps the last good snapshot when a full fetch fails

## Usage

- **Left click** the bar text — open the panel
- **j / k** — move selection
- **Enter** — open TradingView for the selected symbol
- **Esc** — close panel

## Symbols

The default list is hardcoded in `bin/market_stats.py`. Edit that file or add a config option in `manifest.json` to customize.

## License

MIT
