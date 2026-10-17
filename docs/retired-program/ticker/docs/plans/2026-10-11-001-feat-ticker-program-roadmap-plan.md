---
title: "Program roadmap: omarchy-ticker (Market Watchlist)"
type: feat
status: active
date: 2026-10-11
---

# Program roadmap: omarchy-ticker

Written directly (not via `ce-plan`): the repo is two files, so the pipeline skill would add ceremony without information. Required fields (status, evidence, dependencies, verification, difficulty, feasibility, simpler alternative) are all present.

## Scope and constraints

- Plugin id `lukedaduke.ticker`; `Panel.qml` (about 340 lines) and `bin/market_stats.py` (about 195 lines).
- The repo is an umbrella subtree: land changes in `omarchy-plugins` first (U2).
- QML cannot be run or linted outside Omarchy (host provides `qs.*`).
- Keep the helper stdlib-only and the last-good-snapshot behaviour.

## Units

### Now

**U1. Replace `preview.png` with a real capture.** Status: open. Evidence: current image shows BTC/SPX rows and a floppy icon not present in code. Dependencies: a running shell session (owner). Verification: image shows real symbols from `TICKERS`.
- Difficulty: easy, one screenshot.
- Feasibility: needs the owner's live Omarchy session; agents here were told not to reload anything.
- Simpler alternative: delete `preview.png` until a capture exists; a wrong image is worse than none.

**U2. Land this program PR's changes in the umbrella.** Status: open. Evidence: `AGENTS.md` provenance section; `publish.sh` fast-forwards `main` and deletes direct commits. Dependencies: owner decision on how docs/brand files (not in the umbrella subtree) are carried. Verification: `scripts/publish.sh ticker` produces a fast-forward containing this PR's files.
- Difficulty: medium, because the subtree split and a docs-only file set interact.
- Feasibility: could block on branch protection in the umbrella and on publish.sh refusing non-fast-forward.
- Simpler alternative: keep `DESIGN.md`, `docs/`, `assets/brand/` in the umbrella plugin directory so the subtree carries them; no special casing.

**U3. UI pass applied (done in this PR).** Status: done. Evidence: commits `ui: panel text follows the shell font family` and `ui: quiet row keylines, stale label, key hints`. Verification: needs a shell reload by the owner; not run here.
- Difficulty: easy.
- Feasibility: QML untestable outside Omarchy.
- Simpler alternative: none; changes are 20 lines.

### Next

**U4. Configurable watchlist.** Status: open (existing roadmap item). Evidence: `TICKERS` hardcoded; `summary` hardcodes GOLD, NVDA, URA. Dependencies: Omarchy settings-schema support in `manifest.json`; U2. Verification: `tests/test_ticker_stats.py` in the umbrella gains a case for a custom list; invalid symbols are dropped, count capped.
- Difficulty: medium: settings schema, validation of untrusted symbol strings (they go into a URL), and keeping `standby` (which reuses `market_stats.py`) working.
- Feasibility: depends on how the Omarchy shell passes settings to a `Process`; may need env or argv, and the safe-PATH rule must hold.
- Simpler alternative: read a single `~/.config/omarchy/ticker.json` list in the helper, no settings UI; most of the value for about 30 lines. Also derive `summary` from the first three rows instead of three hardcoded symbols.

**U5. Market-state labelling (open/closed, pre/post).** Status: open. Evidence: only `regularMarketPrice` and `chartPreviousClose` are read. Verification: fixture payloads with `marketState` values.
- Difficulty: easy to medium: one more field from the same response, one chip state.
- Feasibility: field availability on the unofficial endpoint is not guaranteed.
- Simpler alternative: show nothing and rely on the `stale` label added in U3.

### Later

**U6. Sparkline row.** Difficulty: medium (needs `range=5d` data, payload bound check against the 300 KB QML cap). Feasibility: more bytes per refresh from an unofficial API. Simpler alternative: a three-colour arrow only.

**U7. Crypto and forex symbols.** Difficulty: easy once U4 lands (Yahoo uses `BTC-USD`, `EURUSD=X`), mostly `format_price` and TradingView symbol mapping. Feasibility: TradingView symbol names differ per exchange. Simpler alternative: document the symbol format for the U4 config and add no code.

**U8. Price-change alerts.** Difficulty: hard: needs a persistent state file, rate limits and notification plumbing outside the widget. Feasibility: the shell may not give a plugin a notification API. Simpler alternative: colour the bar summary urgent when any row moves beyond a threshold; no notifications.

**U9. Decide on a quote source.** Difficulty: medium. Feasibility: the Yahoo endpoint is undocumented; alternatives (Stooq CSV, Finnhub free tier) have their own terms and keys. Simpler alternative: keep Yahoo and add a clear failure message; already done in the helper.

## Simplifications found

- `quote_item` builds the failure dict twice with the same five placeholder fields (deadline path and exception path); one helper removes about 20 lines in `bin/market_stats.py`.
- `chipFill` and `chipText` in `Panel.qml` are two functions over one conditional; inline or merge.
- `summary` hardcoding three symbols (`collect`) goes away with U4.

## Verification

Run from the umbrella: `python3 scripts/validate-manifests.py`, `python3 -m pytest tests/test_ticker_stats.py -q`. Standalone here: `python3 -m py_compile bin/*.py`, `python3 -m json.tool manifest.json`.
