# Review: lukedaduke.ticker (omarchy-ticker)

Reviewed: f8db38c · 2026-09-17 · verdict: SHIP

## Findings

### Low
- [LOW] README.md:5-32 — no removal instructions or dependencies section (install says `omarchy plugin add`; nothing on `omarchy plugin remove` or the python3/network requirement) — add a Remove + Requirements block.
- [LOW] Panel.qml:76-115 — helper stderr is never collected; a python crash surfaces only as "quotes helper exited 1" with no diagnostics — add a `stderr: StdioCollector` and log/truncate it into `fetchError`.
- [LOW] bin/market_stats.py:73-74 — `meta.get("regularMarketPrice") or 0` turns a missing price into a fake `$0.00 / -100.00%` quote instead of a failure — treat absent price as an error path.
- [LOW] bin/market_stats.py:94-96 — the Content-Type gate is bypassed when the header is absent (`if content_type and ...`); a non-JSON body without a declared type slips through to `json.loads` — require a JSON type when the header is present-or-absent, or drop the gate and rely on the parse.
- [LOW] Panel.qml:167 — pressing `j` with an empty `marketItems` sets `selectedIndex = -1` (`Math.min(-1, 1)`); visually harmless but sloppy — clamp to `Math.max(0, len - 1)`.

### Info
- [INFO] Panel.qml:54 — `tv_sym` is concatenated into the TradingView URL unencoded; safe today (values come from the static TICKERS table, scheme hardcoded `https://`) but fragile if the watchlist ever becomes configurable — `encodeURIComponent()` the symbol.
- [INFO] Panel.qml:146 — `barSummary` (remote-derived) reaches `BarIconButton.tooltipText`, whose internal rendering can't be verified for `PlainText`; values are number-formatted so risk is nil — note only.
- [INFO] tests/test_ticker_stats.py — 3 tests pass (`uvx --with pytest pytest`), covering price/change mapping, success shape, and full-network failure; no coverage of the deadline path, `clean_text`, HTTPS-redirect refusal, or byte budgets — worth adding.
- [INFO] bin/market_stats.py:115-124 — per-item failures emit `positive: true`, so a failed quote renders "--" in a green chip in the grid — cosmetic.

## Marketplace readiness
- manifest.json ✓ (valid JSON; id `lukedaduke.ticker`, kinds `bar-widget`, `entryPoints.barWidget` → Panel.qml exists)
- README ✓ install/usage · ✗ removal · ✗ dependencies
- LICENSE ✓ MIT · preview.png ✓ 1280×720 PNG
- Helper `bin/market_stats.py` present and identical to the umbrella-repo copy the tests target

## Positives
- Exec hygiene: absolute tool paths (`/usr/bin/python3`, `/usr/bin/xdg-open`) with an explicit PATH-shadow rationale comment; `clearEnvironment: true` + whitelist env (`PATH=/usr/bin:/bin`, `LC_ALL=C`); argv arrays everywhere, no shell.
- Network: hardcoded https + runtime scheme check (market_stats.py:81), `HTTPSOnlyRedirectHandler` refuses non-https redirects, JSON Content-Type gate, dual byte budgets — 1 MiB producer-side pre-check + bounded read, 300 KB consumer-side.
- Untrusted data: `clean_text` strips control chars and caps at 120 chars for remote-derived strings; every dynamic `Text` in the panel is `textFormat: Text.PlainText` (verified all 5 bindings); JSON parse wrapped in try/catch.
- Deadline design: layered and correctly ordered — helper job deadline 45s < panel SIGKILL 50s < helper SIGALRM 60s ≤ refresh 60s; kill path can't leave orphans.
- Helper↔panel contract verified both directions: panel reads `summary/items/updated_str/ok/error` and item fields `symbol/price/change/positive/tv_sym` — all emitted; stale-data handling keeps last good snapshot; `selectedIndex` re-clamped on refresh.
- Theme-clean: `qs.Commons` Color/Style only, zero hardcoded hex (grep-verified).
