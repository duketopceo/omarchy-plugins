# Review: io.github.duketopceo.numbat (omarchy-numbat)
Reviewed: e744b54 · 2026-09-17 · verdict: SHIP-WITH-FIXES

## Findings

### Medium
- [MED] Panel.qml:169 + Service.qml:318 — both QML watchdogs kill the probe at 14s, but the helper's own worst case is ~28–30s (SCAN_TIMEOUT_S=25 + HOOKS_TIMEOUT_S=3, JOB_DEADLINE_S=30, probe_numbat.py:38-41). A `numbat scan` slower than 14s gets the whole tree group-killed before the single-shot `stdout.write` at probe_numbat.py:806 — so even the already-collected tail findings/events are discarded and the panel can sit at "probing numbat…" indefinitely on a loaded box (service toasts starve the same way). Raise the QML deadlines past JOB_DEADLINE_S (~32s) or drop SCAN_TIMEOUT_S below the watchdog so the helper always finishes and emits a degraded packet.

### Low
- [LOW] bin/probe_numbat.py:761-763 — `findings_24h` is recounted over `merged`, which is already capped at MAX_FINDINGS=20, so >20 in-window findings report as "20 findings/24h"; the full count computed in `_summarize_records` is discarded. Keep the summary count and add the live-only delta, or count before the cap.
- [LOW] bin/probe_numbat.py:785 — `active_agents`/`agents_seen` are populated only from the scan-cache summary; live records.ndjson events are never folded into the agents map, so the Activity tab can lag the Log tab by up to SCAN_INTERVAL_S (10min) even while events stream. Merge in-window live events into the agents dict before emitting.
- [LOW] bin/probe_numbat.py:532 — hook-status parsing uses substring `"install" in line` plus a positional `"not" not in split()[1:3]` check; a row like "codex uninstalled" (substring match, no "not" token) is counted as wired → false LIVE/hooked coverage claim. Match whole tokens instead (e.g. `tokens[1] == "installed"`).
- [LOW] bin/probe_numbat.py:589-593 — `_fresh_enough` only checks `now - mtime < 600`; a cache with mtime ahead of the clock (NTP step-back, preserved mtimes) stays "fresh" for skew+interval, serving stale scan data longer than intended. Add a future-mtime bound (e.g. `mtime - now > skew → stale`).

### Info
- [INFO] bin/probe_numbat.py:684 — on a successful scan with a failed `numbat hook status`, `hooked_agents` is cached as [] → `hooks_seen` false → spurious SETUP banner until the next cycle; consider carrying forward the prior cache's list on hook-status failure.
- [INFO] bin/probe_numbat.py:79-97 — `_kill_tree` only signals the direct child; descendants rely on the QML watchdog's group-kill (setsid contract is honored, so this is as designed — noted for completeness).
- [INFO] bin/probe_numbat.py:40 — `int(os.environ.get("NUMBAT_SCAN_INTERVAL_S", ...))` is unvalidated; a bad value crashes the helper at import (dev-only path — production env is cleared).
- [INFO] bin/probe_numbat.py:658/673 + Panel.qml:460 — `records_path` always renders "~/.numbat/findings.ndjson" even when only records.ndjson exists; `live_records_path` is emitted but unused by the panel footer.
- [INFO] bin/probe_numbat.py:567 — `_load_scan_cache` lstats the cache by path after validating dirfd; harmless same-user TOCTOU nit — could stat via the open directory fd instead.

## Marketplace readiness
- manifest.json ✓ — schemaVersion 1, id matches repo/dir, kinds [service, bar-widget], entryPoints.service→Service.qml + entryPoints.barWidget→Panel.qml both present, complete barWidget block
- README.md ✓ — install/remove/external deps (numbat release tarballs, AUR name collision warning, optional `hook install`)
- LICENSE ✓ — MIT
- preview.png ✓ — 30KB
- Tests ✓ — omarchy-plugins/tests/test_numbat.py: 34 cases covering contract keys, stale/fresh cache, scan failure, symlink refusal, dedupe, control-char clipping, bounded tails, and the `tail` verb
- UPSTREAM.md ✓ (bonus) — documents upstream tool provenance, license split, and observe-only scope

## Positives
- Descriptor-relative I/O throughout: `O_NOFOLLOW` + owner + regular-file checks on `~/.numbat`, both record sinks, and the state dir
- Atomic 0600 cache publish via `O_EXCL` temp + `os.replace` under dirfd; writes stay under `~/.local/state/omarchy/numbat/`, never `~/.numbat`
- Exec hygiene: fixed `/usr/bin/python3` + `/usr/bin/kill`, argv arrays (no shell), `clearEnvironment` + minimal env with HOME dropped (resolved via passwd), byte-capped nonblocking drains with deadlines
- Layered kill contract: helper `os.setsid()` + SIGALRM self-deadline, QML watchdog group-kills `-pid` then signals the child
- Untrusted data is cleaned end-to-end: control-char normalization + length caps helper-side, and every QML Text is `Text.PlainText` (23/23 Panel, 4/4 Service)
- Toast storm prevention done right: stat-only 5s tail verb, persisted `lastSeenFinding` watermark with silent first-poll baseline, max-3 bounded stack, coalesced probe reruns
- Zero network surface, zero secrets, observe-only by contract (never runs `hook install`, never writes under `~/.numbat`)
- Injectable seams (`tool`/`run`/`numbat_home`/`state_dir`/`now`) backed by a real test suite
