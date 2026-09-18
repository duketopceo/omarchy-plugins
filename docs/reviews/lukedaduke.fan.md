# Review: lukedaduke.fan (omarchy-fan)

Reviewed: 3c85c92 · 2026-09-17 · verdict: SHIP-WITH-FIXES

## Findings

### High
- [HIGH] Panel.qml:58-64 + bin/system_monitor_stats.py:572-580 + bin/omarchy-fan-set:39-44 + bin/omarchy-fan-daemon:181 — the stats `Process` runs with `clearEnvironment: true` and a scrubbed `procEnv` that drops `XDG_RUNTIME_DIR`, so `read_fan_mode()` falls back to `~/.local/run/omarchy-fan/current_fan_mode`. But `omarchy-fan-set` is spawned via `execDetached` with the full shell env and writes `$XDG_RUNTIME_DIR/omarchy-fan/current_fan_mode` (`/run/user/<uid>/...`) — the same path the daemon reads. The collector therefore reads a file that is never written: `data.fan_mode` is always `"auto"` and Panel.qml:184-185 resets `currentMode` to AUTO on every 5 s refresh, so the mode badge, preset buttons, and right-click cycling can never display/persist a chosen mode even though the daemon honors it. Keep `XDG_RUNTIME_DIR` in `procEnv` (it is the user's own dir; scrub `HOME`/`PATH` only) or make both helpers resolve one fixed path.

### Medium
- [MED] bin/system_monitor_stats.py:653 + Panel.qml:236,348-365,629-654 — `fan_control` is `(bin/omarchy-fan-set).is_file()`, which is always true after install, so all fan controls render enabled even with no daemon running and no writable hwmon — clicks write a mode file nothing consumes. Detect real capability (daemon heartbeat/pidfile, writable `pwm*`/`fan*_target`) and surface "READ" honestly.
- [MED] repo contents — `bin/omarchy-fan-daemon` ships but nothing installs or starts it: no systemd unit, no launcher, no docs (the umbrella copy has `omarchy-fan-daemon.service` + `omarchy-fan-daemon-start` that were never synced here). README.md:19,30 advertises daemon-driven auto/custom curves, so a fresh `omarchy plugin add` gets a marquee feature that cannot work. Ship the unit + install steps or drop the claim.

### Low
- [LOW] bin/omarchy-fan-set:21-24,45-48 — `_open_dir` raises uncaught `PermissionError` on a symlinked/non-owned runtime dir and `os.mkdir(target)` dies with `FileNotFoundError` if `~/.local/run` is missing (XDG-less invocation); fails closed but exits with a raw traceback. Catch and exit non-zero cleanly.
- [LOW] bin/system_monitor_stats.py:237-241,260-279 — `ps -eo pid,comm,rss,pmem` is not newline/space safe: a `comm` containing `\n` injects an attacker-chosen row (spoofed `pid` → `x` kills an arbitrary own-uid pid), and spaces in `comm` skew `rss`/`pmem` parsing. Reject rows where `parts[0]` isn't a clean int and strip control chars from `comm` helper-side (panel `clipStr` already strips them display-side).
- [LOW] bin/system_monitor_stats.py:209 — `int(value.strip().split()[0])` raises `IndexError` on a value-less `/proc/meminfo` line, killing the whole `collect()` → empty stdout → panel shows "empty stats". Parse each line in try/except.
- [LOW] bin/system_monitor_stats.py:655 — `top_cpu()` spawns a second `ps` on every 5 s refresh but `top_cpu` is never read by Panel.qml — permanent wasted exec. Drop the key or render it.

### Info
- [INFO] Panel.qml:384,422,456,475,505,563,622,757,766,799 — several `Text` sinks lack `textFormat: Text.PlainText`; today every interpolated value is an int or `clipStr`'d (which strips `<`/`>`), so AutoText can't see markup — set `PlainText` anyway for defense-in-depth.
- [INFO] Panel.qml:180 — `root.fetchError = data.error` is stored/displayed unclipped (sink is `PlainText` and the helper is local, so cosmetic); run it through `clipStr` for consistency.
- [INFO] bin/kill_proc.py:16 — SIGKILL immediately, no SIGTERM grace period. Deliberate for a "force kill" UI presumably; note that `x` gives no chance to flush state.
- [INFO] bin/system_monitor_stats.py:598 + bin/omarchy-fan-daemon:208 — `custom-*` mode strings are accepted by both readers, but `omarchy-fan-set` only ever writes `custom`; if one appears, Panel.qml:185 stores it raw and `cycleMode`/the badge treat it as unknown → AUTO. Harmless forward-compat; consider parsing the suffix into `customName`.
- [INFO] tests/test_fan_stats.py exists and covers `collect()` bounds, empty hwmon, `kill_pid` refusal, and daemon descriptor checks — but nothing exercises `omarchy-fan-set`/`_runtime_dir` path agreement, which is exactly where the HIGH above slipped through. Add a path-consistency test.

## Marketplace readiness
- manifest.json: ✓ (id `lukedaduke.fan`, kinds `bar-widget`, `entryPoints.barWidget` → `Panel.qml` present, version/license/description set)
- README.md: partial — install + usage + license present; no remove/uninstall section; Requirements misses `python3`, `btop`/`omarchy-launch-or-focus-tui`, and any daemon setup (see MED above)
- LICENSE: ✓ (MIT)
- preview.png: ✓ (129 KiB)
- Tests: ✓ (`omarchy-plugins/tests/test_fan_stats.py` covers this plugin's helpers)

## Positives
- Collector exec posture is exemplary: absolute `/usr/bin/python3`, `clearEnvironment: true`, minimal explicit env, argv-only (no shell), `StdioCollector` with 300 KB cap + JSON try/catch + `ok:false` path, and a 9 s `SIGKILL` deadline layered over the helper's own 8 s `SIGALRM` self-kill (Panel.qml:159-262, bin/system_monitor_stats.py:659-665).
- `_run()` resolves tools under a fixed `SAFE_PATH`, scrubbed env, own process group, per-call timeout, 256 KiB output cap, `stderr`→devnull, and TERM→KILL tree reaping (bin/system_monitor_stats.py:36-116).
- File writes are textbook: dirfd-relative `O_NOFOLLOW`/`O_DIRECTORY` opens with uid checks, `O_EXCL` pid-named temp + `fsync` + atomic same-dir rename, `0o700`/`0o600` (bin/omarchy-fan-set:17-53); daemon re-validates dir/file uid, type, and size before trusting mode/curve bytes (bin/omarchy-fan-daemon:190-256).
- All untrusted strings pass `clipStr` (control chars + `<>` stripped, length-capped) before reaching `Text` sinks; nearly every `Text` is `PlainText`; numeric fields are individually clamped (Panel.qml:105-110,166-241).
- `kill_proc.py` refuses `pid <= 1` and the panel re-guards it; `omarchy-fan-set` maps any unrecognized argv to `auto` (fail-safe default).
- No network, no secrets, no hardcoded colors — all `Color`/`Style`/`bar.foreground`-derived.
