# Review: lukedaduke.agents (omarchy-agents)
Reviewed: 06a3626 · 2026-09-17 · verdict: NEEDS-WORK

## Findings

### High
- [HIGH] Main.qml:221 — `providerEnabled()` allowlist omits `fireworks`, so the provider advertised in manifest.json:8/33 and wired in Panel.qml:100-101 (`fireworks.ai` login URL, `fireworks.svg`) can never appear: for any record with id `fireworks` the function returns `enabled !== false && !!allowed["fireworks"]` → `false`. The same map also silently default-enables `cursor/devin/openrouter/agy/a0`, which are absent from manifest `defaults.providers` — code and manifest disagree in both directions. Recommendation: reconcile `allowed` with the manifest provider set (add `fireworks`, declare or drop the extras).
- [HIGH] Panel.qml:470,559,615,626,707,813,842,928,985,1020,1053 — no `Text` in the plugin sets `textFormat: Text.PlainText`; every binding falls back to `Text.AutoText`, which auto-detects markup. `providerName`, `usageStatusText`, `authHelpText`, model ids (via `friendlyModelName`), and `day.date` all come from JSON records, and `providerName`/`stats.*` additionally come from synced snapshot files written by other machines into a shared sync folder (Main.qml:471-510). A crafted `<img src=...>`/`Provider <b>X</b>`-style string renders as rich text — UI spoofing plus silent remote fetches from inside the shell. Recommendation: set `textFormat: Text.PlainText` on every Text/PanelToolTip bound to record- or sync-derived strings.

### Medium
- [MED] Main.qml:128-144, 24-33, 324-356 — no deadline on any `Process`. If `omarchy-agent-usage-update` (or `find`, `mkdir`, the bash scan) hangs, `updateProcess.running` stays true forever and every later `runUpdate()` just folds into `pendingUpdateKind` — the widget goes stale with no error. Recommendation: add a watchdog `Timer` per process that kills and re-queues on timeout.
- [MED] Main.qml:147 — hard runtime dependency on `~/.local/bin/omarchy-agent-usage-update` (plus `omarchy-launch-tui`/`omarchy-agent`/`cursor` in Panel.qml:65-101) that this plugin does not ship and never checks for; a missing binary leaves the bar icon hidden and the panel empty with no user-facing error. Recommendation: existence-check the helper (`test -x`/`FileView`) and surface a `usageStatusText`-style message; document the dependency in README.
- [MED] Main.qml:432-434 — sync scan is `bash -c` over `cat "$dir"/*.json` with the entire output buffered by `StdioCollector` and `JSON.parse`d: no per-file size cap, and `cat` follows symlinks (`-f` passes for a symlink to a regular file), so any regular-file target on the filesystem gets pulled into the shell process's memory from a potentially shared folder. Recommendation: replace with `find "$dir" -maxdepth 1 -type f ! -type l -name '*.json' -size -1M` plus a `head -c` cap, and skip non-regular files.
- [MED] Main.qml:153,156 + Panel.qml:83 — unvalidated strings reach helper argv: `record.id` (content of files in the usage dir) is appended as a positional arg to `omarchy-agent-usage-update` and to `omarchy-agent <id>`; `settings.providers` keys follow `--except`. Array-form exec blocks shell injection, but an id like `--force` or `--except` still injects flags. Recommendation: gate ids/`--except` values through `^[A-Za-z0-9_.-]+$` before appending.

### Low
- [LOW] Main.qml:471-505,590-634 — synced snapshots are unauthenticated: any writer to the shared sync dir can forge `providers`, `deviceId`, or `scope` and spoof merged totals; the `===path===`/`=== EOM ===` framing can also be split by file content containing those marker lines. Recommendation: key snapshots by verified filename↔deviceId, ignore embedded marker lines via a stricter frame (e.g., length-prefixed or per-file FileView reads).
- [LOW] Panel.qml:727,760,796 — no length caps on record-derived collections (`limits`, `recentDays`, `modelUsage` keys are iterated in full before `slice(0,4)`); a malformed record/snapshot builds unbounded delegates. Recommendation: cap arrays/dicts at parse time (e.g., 16 limits, 31 days, 64 models).
- [LOW] Main.qml:117 — `refreshIntervalSec` = `Math.max(30, Number(setting(...)))` yields `NaN` for a non-numeric manual setting, leaving the refresh `Timer` with a NaN interval. Recommendation: `var n = Number(...); interval: isFinite(n) ? Math.max(30,n)*1000 : 900000`.
- [LOW] README.md — no removal instructions and no explicit dependency/configuration docs (helper binary, `syncMode`/`syncDir` semantics, provider allowlist). Recommendation: add `omarchy plugin remove lukedaduke.agents`, a "Requires `omarchy-agent-usage-update` (ships with Omarchy)" note, and a sync-setup section.

### Info
- [INFO] Process hygiene is otherwise decent: all exec is argv-array form (no `shell=True`-style interpolation); the single `bash -c` passes the directory via `$0` with consistent quoting (Main.qml:432-433); all `xdg-open` targets are literal `https://` URLs (Panel.qml:95-101) — no untrusted scheme reaches the opener.
- [INFO] No secrets are handled by the plugin — no API keys/tokens in argv, files, or the repo. Helper stderr is mirrored to `console.warn` (Main.qml:142,354); if the upstream helper ever logs tokens they land in the journal.
- [INFO] Contract assumption: `limits[].percent` is treated as a 0–1 fraction (Panel.qml:47,855,868) and `resetsAt` as a `Date`-parseable string — cannot be verified because the emitting helper lives outside this repo; a 0–100 scale would saturate every meter and alarm.
- [INFO] `Agent.qml:16-23` watches usage-dir JSON via `FileView` with `printErrors:false` and try/catch `JSON.parse`; `onLoadFailed` nulls the record — missing/empty/corrupt records degrade gracefully.
- [INFO] Panel.qml:404,411 — right-click and left-double-click both hardcode `launchAgent("openrouter")` regardless of the selected provider; functional but undocumented.
- [INFO] `assets/` ships marks for claude/codex(±light)/cursor/devin/factory/fireworks/openrouter; `agy`/`a0`/`groq`/`hermes` fall back to the bar glyph (Panel.qml:329-336,507) — graceful, but `fireworks.svg`/`factory.svg` are dead weight while the allowlist excludes both ids.
- [INFO] Repo contains zero collectors — it is purely a renderer over `~/.local/state/omarchy/agents/usage/*.json` (Main.qml:16,24-33). Correctness of the helper↔panel JSON contract is therefore only verifiable on the read side, which is uniformly defensive.

## Marketplace readiness
- manifest.json: ✓ — valid `schemaVersion:1`, id `lukedaduke.agents` matches repo/folder, `kinds:["bar-widget"]`, `entryPoints.barWidget:"Panel.qml"` exists on disk, settings schema + defaults present. Caveat: provider defaults drift from code allowlist (see High #1).
- README.md: partial — install command and honest "read-only renderer" description, but no remove step, no dependency list, no sync-config docs.
- LICENSE: ✓ MIT (Luke Kimball, 2026).
- preview.png: ✓ present (1280×720 PNG).
- Tests: ✗ none for this plugin in `omarchy-plugins/tests/` (only generic `test_manifests.py` coverage plus unrelated per-plugin tests). The plugin ships no `bin/` helpers, so there is little unit-testable surface; QML-side logic (window parsing, aggregation) is untested.
- Note: `manifest.json` declares `"omarchy": {"clonedFrom": "omarchy.agents"}` and ROADMAP.md self-assesses "not ready for an aggressive marketplace launch" — this is a personal fork of the stock widget; differentiation vs. the upstream plugin is thin.

## Positives
- Every `Process`/`execDetached` call uses fixed argv arrays — no string-built commands; the one `bash -c` is correctly parameterized via `$0`.
- All outbound URLs are compile-time `https://` literals; no user/record data reaches `xdg-open`.
- Sync snapshot path handling is careful: `safeSnapshotFileName`/`safeDeviceId` strip separators and metacharacters, `FileView` uses `atomicWrites:true`, and `~`/`$HOME`/relative expansion is explicit (Main.qml:301-304,444-469).
- Read side is defensively coded throughout: `Array.isArray`/`Number()` coercion/`||`-defaults everywhere, JSON.parse in try/catch, `providerIndex` resolved by stable provider id rather than position (Panel.qml:22-30).
- Theme-clean: zero hardcoded colors or fonts; all styling via `qs.Commons` `Color`/`Style`.
- Nice operational details: `retryAdvised` triggers a per-agent 30 s limits retry, queued refreshes collapse to a single rerun with `force` outranking, and disabling sync fully resets aggregate state.
