# Review: io.github.duketopceo.bumblebee (omarchy-bumblebee)
Reviewed: 5beb460 · 2026-09-17 · verdict: SHIP-WITH-FIXES

## Findings

### Medium
- [MED] bin/scan_bumblebee.py:686-704 + Service.qml:228 — `collect_age` hardcodes `"ok": True, "error": None` and re-emits the cached `exposures`/`exposure_ids` without propagating the cached payload's `error`. A failed scan republishes the cache with `exposures: []` (collect() writes the error payload at scan_bumblebee.py:668), so the hourly `age` probe produces a clean-looking empty result; `diffNow` (Service.qml:140-156) then runs `persistLastSeen([])` unconditionally and clobbers the real watermark. The next successful scan sees `seen=[]` → every known exposure toasts as "new" (up to 3 stacked), and a first-ever poll on an error cache silently discards the silent-baseline guarantee. Mirror the scanProc guard (`if (data.error) return`, Service.qml:263) in the age path — but that requires the helper to emit the cached `error`/`ok` first, since the age payload currently masks both.
- [MED] bin/refresh_catalog.py:83,94 — the `https://` scheme gate checks only the input URL; `urllib.request.urlopen` follows redirects with the default opener (including downgrades to `http://`/`ftp://`), and `resp.geturl()` is never re-validated. The documented integrity boundary is "repo+tag+TLS", but a redirect to plaintext (upstream misconfiguration/compromise) silently drops TLS and the tarball is then trusted as pinned threat intel — forged advisories land in catalog.d and are passed to bumblebee and the panel as authoritative. Re-check the final response scheme after `urlopen`, or install a redirect handler that rejects non-https targets.

### Low
- [LOW] bin/scan_bumblebee.py:202-209 + Panel.qml:80-86 / Service.qml:46-52 + README.md:29 — `BUMBLEBEE_SCAN_INTERVAL_S` is read from the helper's env, but both QML exec contracts run `clearEnvironment: true` with a fixed env that drops it — the documented override only works for manual CLI runs, never through the panel or service. Document it as CLI-only or add a settings file under plugins-data.
- [LOW] Service.qml:154-155 — `persistLastSeen(ids)` runs on every fresh-cache diff even when the id set is unchanged, so the hourly poll performs a read-modify-write + atomic rename of shell.json (plus FileView reload fan-out to every plugin watching it) for a no-op. Skip the write when `ids` matches `seen`.
- [LOW] bin/scan_bumblebee.py:476 vs Service.qml:85-90 — the helper clips each assembled exposure id to 200 chars (`key[:200]`); the QML `exposureId()` builds the same key without the clip, so for a >200-char id the toast's `names[eid]` lookup misses and the toast falls back to the raw truncated `name|eco|pkg@ver` id instead of the friendly name. Apply the same `key.substring(0, 200)` clip.
- [LOW] bin/refresh_catalog.py:56,387 vs bin/scan_bumblebee.py:55 — the merged `upstream.json` write is unbounded (up to MAX_ENTRIES=20000 entries, ~8MiB worst case) while the scan helper counts catalog files under CATALOG_MAX_BYTES=1MiB; once upstream grows past 1MiB (currently ~370KiB) `catalog_sources.upstream` reports 0 and `catalog_entries` undercounts even though the file is still passed to bumblebee via `--exposure-catalog`. Align the caps or bound the merged write by bytes.

### Info
- [INFO] Panel.qml:238-245 — the 60s `refreshTimer` spawns `python3` for the widget's whole lifetime even when the dropdown never opens (~1440 execs/day); the service's hourly age probe already keeps the cache fresh, so the panel cadence could gate on `opened`. Each run is a cheap cache-stat, so this is a battery/perf nit only.
- [INFO] bin/scan_bumblebee.py:637-640,654 — an empty stdout + exit-0 scan emits `ok:true` / log status `complete` (a zero-record run is indistinguishable from a clean `--findings-only` scan; the tolerance is codified by `test_corrupt_cache_triggers_scan`). A broken shim printing nothing also reads "complete" — consider a distinct `no_records` log status for observability.
- [INFO] bin/scan_bumblebee.py:143-157,176-177 — if the direct child exits but a descendant holds the stdout pipe, the drain exits at the deadline and `proc.poll() is not None` skips `_kill_tree`, so a detached grandchild can outlive the deadline. Bounded by bumblebee's own behavior; noted for completeness.
- [INFO] bin/scan_bumblebee.py:390 vs bin/refresh_catalog.py:246-252 — `_catalog_stats` uses `os.listdir` on `catalog.d` and follows a symlinked directory, while refresh's `_open_dir` rejects one (`O_NOFOLLOW` + uid check). Same-uid threat model makes this cosmetic, but the asymmetry is worth a comment.
- [INFO] bin/scan_bumblebee.py:239-248 / bin/refresh_catalog.py:255-265 — `_publish` fsyncs the temp file but not the containing directory after `os.replace`; a crash can lose the rename. Marginal durability nit.
- [INFO] Panel.qml:70-75 / Service.qml:37-42 — `pluginRoot` strips `file://` but never percent-decodes; a plugin path containing spaces or `%` breaks helper exec (ENOENT → permanent SETUP state). Rare under `~/.config/omarchy/plugins`.
- [INFO] Service.qml:162 — toast row `stamp` is stored but never rendered; `catalog_sources` (scan_bumblebee.py:594-598) is emitted per the contract but never read by the panel. Dead payload fields, or intentional headroom.
- [INFO] bin/refresh_catalog.py:360-362 — `if len(entries) >= MAX_ENTRIES: break` exits only the inner per-document loop; remaining members keep parsing (bounded by MAX_MEMBERS). Harmless wasted work.

## Marketplace readiness
- manifest.json ✓ — schemaVersion 1, id matches repo/dir, kinds [service, bar-widget], entryPoints.service→Service.qml + entryPoints.barWidget→Panel.qml both present, complete barWidget block; umbrella validator: `ok: 10 manifests`
- README.md ✓ — install/remove/external deps, catalog merge path, opt-in refresh, and an explicit privacy/security posture section
- LICENSE ✓ — MIT (matches manifest)
- preview.png ✓ — 1280×720 PNG, 32KB
- Tests ✓ — omarchy-plugins/tests/test_bumblebee.py: ~40 cases across both helpers (missing-binary degrade, stale/fresh cache, NDJSON tolerance, control-char clipping, caps, tar traversal/symlink rejection, schema validation, counts-only output, age verb, watermark ids, atomic 0600 modes); umbrella .pytest_cache lastfailed={} — all green on last run; CI runs pytest on x86 + arm
- UPSTREAM.md ✓ (bonus) — upstream tool provenance, Apache-2.0 split, per-arch install commands, integrity-boundary statement

## Positives
- Descriptor-relative I/O end-to-end: `O_DIRECTORY|O_NOFOLLOW` + uid checks on dirs, `O_NOFOLLOW` + regular-file + uid + size caps on every file read, `O_EXCL` temp + `os.replace` under dirfd for 0600 publishes (cache, scan log, upstream.json)
- Exec hygiene: fixed `/usr/bin/python3` + `/usr/bin/kill`, argv arrays only (no shell anywhere), `clearEnvironment` + minimal env with HOME dropped so the helper resolves home via passwd, tool lookup confined to SAFE_PATH
- Layered kill contract done right: helper `os.setsid()` + SIGALRM backstop; QML watchdogs group-kill `-pid` with deadlines set just above the helper's own (35s vs 30s, 30s vs 25s, 8s for the stat probe)
- `_run` is a genuinely careful subprocess wrapper: selector-driven nonblocking drain, producer byte cap, killpg tree reaping, and a post-exit drain bounded by the same deadline so a pipe-holding descendant can't stall it
- Offline-by-default network: the only call is the opt-in refresh — pinned repo+tag, scheme gate, timeout + byte cap, sanitized tar extraction (traversal/absolute/symlink/non-regular members rejected, member+total+count caps), 0.1.0 schema validation, atomic 0600 merge, counts-only stdout (test-verified never to print advisory bodies)
- Untrusted data cleaned end-to-end: `_clean` strips control chars and clips every emitted string; every QML Text is `Text.PlainText` (27/27) with payload-size caps before JSON.parse; zero hardcoded hex colors — palette is `Color.*`/`Style.*` + alpha fills only
- Watermark-diff design: silent first-observation baseline, failed scans don't advance the watermark on the `--force` path, max-3 toast queue with overflow trim, click-through Overlay-layer windows on every output
- Helper↔panel contract documented at the top of both helpers and it matches what the QML reads; injectable `run`/`fetch`/`home`/`now` seams backed by a real, passing test suite
