# Review: lukedaduke.power (omarchy-power)

Reviewed: b9f06df · 2026-09-17 · verdict: SHIP-WITH-FIXES

## Findings

### Medium
- [MED] Panel.qml:164,174,268-283 — `systemProc` runs `omarchy-system-stats` on every 5s refresh while the panel is open, but `systemInfo` (Panel.qml:18) is never rendered anywhere — dead property plus a wasted process spawn (the helper itself shells out to `top -bn1`). Remove `systemProc`/`systemInfo` or render the data.
- [MED] tests/ — no test file for `battery_helper.py` in the umbrella repo (`omarchy-plugins/tests/` has `test_fan_stats.py`, `test_ticker_stats.py`, etc. for sibling plugins). Add `test_battery_helper.py` covering `make_ascii_graph`, `update_history` append/trim rules, and `_read_history` malformed-input paths.

### Low
- [LOW] battery_helper.py:105,138 — `_read_history` validates the payload is a list but not element shape; a history entry that isn't a dict (or lacks `cap`/`time`) crashes the whole helper via `.get`/`p["cap"]`/`now - "x"`, yielding zero output until the file is removed. File is `0o600` in the user's own state dir so this is self-inflicted only — still, filter elements with `isinstance(p, dict)` and `int(p.get("cap", 0))` on read.
- [LOW] battery_helper.py:59-61 + Panel.qml:330-336 — on a battery-less machine `get_current_battery` returns the default `cap=50, "Discharging"` and the always-on 60s sampler records synthetic points forever; the history file fills with fake data even though the panel can never open. Skip sampling when no `/sys/class/power_supply/*` battery exists (or return early in `--sample` mode).
- [LOW] battery_helper.py:90-122 — read-modify-write on the history file is not locked; the panel-refresh helper and the 60s `--sample` helper can overlap, and last-writer-wins via rename can silently drop a sample. Take a `flock` on the dirfd or a lockfile across the read→write window.

### Info
- [INFO] battery_helper.py:269-275 — emitted keys `capacity`, `status`, `spark`, and `top_consumers[].mem`/`.cpu_num` are never read by the panel (capacity/status come from UPower; only `ascii_graph` and `top_consumers[].name/cpu/bar` are consumed). Harmless dead payload — trim or document.
- [INFO] Panel.qml:204 — `IpcHandler.target: "omarchy.power"` does not match the module namespace `lukedaduke.power`; deliberate per README/comment (one handler per target, `manageIpc: false`), but it can collide with any other plugin registering `omarchy.power` — whichever loads first wins the keybinds.
- [INFO] Panel.qml:142-149 — `pluginRoot` is built from `Qt.resolvedUrl(".").toString()` which keeps percent-encoding; a plugin path containing spaces/non-ASCII would break the helper exec. Non-issue under `~/.config/omarchy/plugins/`, but `Qt.urlToLocalFile`-style decoding would be more robust.
- [INFO] battery_helper.py:15 — `STATE_DIR.mkdir` uses default umask perms for the directory (the history file itself is correctly `0o600`); consider `mode=0o700` for defense-in-depth.
- [INFO] battery_helper.py:41 — single `os.read` isn't guaranteed to return all requested bytes; in practice fine for a ≤64 KiB regular file, and failure degrades safely to `[]`.

## Marketplace readiness
- manifest.json: ✓ (id `lukedaduke.power`, kinds `bar-widget`, `entryPoints.barWidget` → `Panel.qml` present, version/license/description set)
- README.md: ✓ (install, remove, features, external deps `power-profiles-daemon` + `omarchy-*` helpers)
- LICENSE: ✓ (MIT)
- preview.png: ✓ (120 KiB)
- Tests: ✗ (no matching test file in `omarchy-plugins/tests/`)

## Positives
- Exec is exemplary: every `Process` uses absolute `/usr/bin/...` paths, `clearEnvironment: true`, a minimal explicit env, argv-only invocation (no shell), and a SIGKILL deadline timer (Panel.qml:234-328). Helper resolves `ps` via `shutil.which` under a fixed `SAFE_PATH`, scrubbed env, own process group, 2s timeout, 256 KiB stdout cap (battery_helper.py:166-211).
- File I/O is textbook-hardened: dirfd-relative `O_NOFOLLOW` opens, uid/type checks on the state dir and history file, `O_EXCL` pid-named temp + fsync + atomic rename, `0o600` (battery_helper.py:21-57).
- All dynamic QML `Text` sinks set `textFormat: Text.PlainText`; every stdout collector enforces a byte cap before parsing (Panel.qml:241-299).
- Helper↔panel contract verified against the real `/usr/bin/omarchy-*` scripts: `percentage/state/rate/size/time/cycles/threshold` keys, `name\t0|1` profile rows, and `setProfile` argv all match.
- Stale-data guards keep the UI stable across plug/unplug transients (Panel.qml:168-189); no hardcoded colors — all `Color`/`Style`/`bar.foreground`-derived.
