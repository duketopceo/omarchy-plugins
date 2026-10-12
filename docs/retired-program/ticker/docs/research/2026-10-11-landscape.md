# Landscape: watchlist quotes in a Linux bar

Date: 2026-10-11. Method: read the code (`Panel.qml`, `bin/market_stats.py`), then a web search; only what the search returned is cited. Nothing was fetched in depth, so treat "does better/worse" notes as hypotheses to confirm.

## Who else does this

| Project | What it is | Source |
|---|---|---|
| cdump/stonks | stocks widget for Awesome WM and Waybar-on-Sway, shell; last push reported as July 2024 | https://github.com/cdump/stonks |
| Waybar custom modules | Waybar has no finance module; a ticker is a custom script module | https://github.com/alexays/waybar |
| quicktick | Python CLI printing a crypto price ticker to stdout (usable as a custom-module source) | https://pypi.org/project/quicktick |
| TradingView widgets | embeddable web ticker widgets (web, not a bar) | https://www.tradingview.com/widget/ |

The search found no existing Quickshell or Omarchy-plugin ticker. That is the gap this repo fills, but it also means there is no peer to benchmark against inside the Omarchy plugin ecosystem.

## What this repo does differently

- A native bar widget in the Omarchy shell, themed from `qs.Commons` (accent, urgent, muted), not a text blob from a script.
- Keyboard-first panel (`j`/`k`, Enter, Esc) with a one-key jump to TradingView.
- Stdlib-only helper with hard bounds: HTTPS-only redirects, 1 MiB body cap, 45 s whole-job deadline, control-character stripping; keeps the last good snapshot on failure.

## What users expect, and gaps

1. A watchlist they can edit. Today the 18 symbols are hardcoded in `bin/market_stats.py` (`TICKERS`). Highest-value gap.
2. Honest freshness. The panel shows a last-updated time but until this pass did not say when quotes were stale.
3. Pre/post-market and closed-market state. The helper requests `interval=1d&range=1d` and reads `regularMarketPrice` against `chartPreviousClose`, so after hours the change is the last session's, not marked as such.
4. A trustworthy data source. Quotes come from Yahoo's unofficial `query1.finance.yahoo.com/v8/finance/chart` endpoint (see `AGENTS.md`). It has no published terms or SLA; it can change or rate-limit without notice. Risk to record, not to fix here.

## Repo-state findings

- `preview.png` is a marketing card showing a floppy-disk glyph and `GOLD / BTC / SPX` rows. BTC and SPX are not in the watchlist and the bar icon is not a floppy disk. It misleads marketplace users and should be replaced with a real capture (roadmap U1).
- The repo is a published subtree of `duketopceo/omarchy-plugins` (`plugins/lukedaduke.ticker/`). Direct commits are overwritten by `scripts/publish.sh`. See roadmap U2: this PR's code and doc changes must also land in the umbrella.
