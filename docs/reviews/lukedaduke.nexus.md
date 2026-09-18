# Review: lukedaduke.nexus (omarchy-nexus)

Reviewed: 82d284e · 2026-09-17 · verdict: SHIP-WITH-FIXES

## Findings

### Medium
- [MED] bin/probe_nexus.py:315 — `elif tran == "usb" or name.startswith("sd")` labels any `sd*` block device as "USB Flash Drive … Ventoy Multi-Boot USB Stick"; on machines with SATA/SCSI disks (`sda`, etc.) a real internal drive renders as a flash stick — gate the flash-drive label on `tran == "usb"` alone and let `sd*` fall through to the generic `Storage ({name})` title.
- [MED] Panel.qml:101 vs bin/probe_nexus.py:11 — deadline contract mismatch: QML group-kills the probe at 5s, but worst-case legitimate helper time is ~6s (three sequential `_run` calls × 2s) and the helper's own SIGALRM is 8s; a slow-but-healthy probe (e.g. `bluetoothctl` near timeout) is killed and its output discarded every tick — raise `statusDeadline.interval` to ≥8s or shorten per-call timeouts so the layers are ordered like lukedaduke.fan's.

### Low
- [LOW] bin/probe_nexus.py:186 — `speed_tag` maps only 10000/5000/480 and defaults everything else to `"12M"`, mislabeling 1.5M low-speed HID devices and 20000 (USB 3.2 Gen 2x2) hardware — extend the map (`1.5`→"1.5M", `12`→"12M", `20000`→"20G") with a generic `speed + "M"` fallback.
- [LOW] tests/ — no `test_probe_nexus.py`; every other shipped helper has a matching test file (`test_fan_stats.py`, `test_ticker_stats.py`, `test_numbat.py`, …) while this plugin's parsing logic (`resolve_device` classification, `bluetoothctl` line split, lsblk tree `walk`, speed map, JSON-shape contract) goes untested — add coverage mirroring test_ticker_stats.py.
- [LOW] Panel.qml:66-93 — `statusProc` has no `stderr` collector, so a crashing/misbehaving probe is indistinguishable from "no hardware found" (same gap flagged on lukedaduke.ticker) — add a `stderr: StdioCollector` and surface a truncated diagnostic.
- [LOW] bin/probe_nexus.py:175-176 — `rf()` uses a bare `except:` and `open()` without a context manager; harmless in a short-lived probe but sloppy — use `with open(p) ...` and `except OSError`.
- [LOW] Panel.qml:114-119 — `refreshTimer` polls every 3s for the lifetime of the bar even when the panel is closed (python3 spawn + up to 3 child processes per tick, ~29k execs/day) — gate on `root.opened` or back off the interval when closed; data is refreshed on open anyway (`BarIconButton.onPressed`).

### Info
- [INFO] bin/probe_nexus.py:135 — `_clip` truncates but never strips control characters, so a USB `product` string containing `\n`/`\x1b` reaches QML verbatim; every Text sink is `Text.PlainText` so markup injection is dead — cosmetic-only (row layout), noted because sibling lukedaduke.fan strips `[\x00-\x1f\x7f-\x9f<>]` consumer-side.
- [INFO] bin/probe_nexus.py:20-36,218-229,258,266-273,309-322 — machine-specific mappings baked into a VERIFIED listing: personal `KNOWN_HARDWARE` dict, `enp0s20f0u1u2u4`→"Dock Gigabit LAN", `PC711`/`SN520` NVMe names, `nordlynx`/`tailscale0` labels, BT name substrings ("mchncl"→"MX Mechanical Keyboard"). All degrade gracefully to generic labels on other hardware — portability note only.
- [INFO] bin/probe_nexus.py:333-338 — `"ok": True` is the only emitted shape; no error field, so a partial helper failure (e.g. `bluetoothctl` down) empties a whole category and flaps the tab counts every 3s rather than holding stale — acceptable, but a per-section `ok`/`error` would be cleaner.
- [INFO] manifest.json:7 / README.md:4 — description promises "Internal Silicon" but no silicon section exists in probe output or panel — copy drift.
- [INFO] bin/probe_nexus.py:92-106 — post-exit drain sets `completed = True` unconditionally, so output collected past the per-call deadline is still returned (bounded by remaining time) — intentional leniency, noted.
- [INFO] bin/probe_nexus.py:287 — `lsblk -o MOUNTPOINTS` requires util-linux ≥ 2.37; README lists `lsblk (util-linux)` unpinned — failure path is graceful (empty storage list).
- [INFO] bin/probe_nexus.py:231 — `mac` is emitted to QML but never rendered — trivial over-disclosure into the shell, local only.

## Marketplace readiness
- manifest.json ✓ (valid JSON; id `lukedaduke.nexus` matches folder, kinds `bar-widget`, `entryPoints.barWidget` → Panel.qml exists, license field MIT)
- README ✓ install (`omarchy plugin add`) · usage · removal · dependencies (python3, bluez-utils optional, iproute2, util-linux)
- LICENSE ✓ MIT · preview.png ✓ 1280×720 PNG
- Helper `bin/probe_nexus.py` present, executable, byte-identical to the umbrella-repo copy (`plugins/lukedaduke.nexus/`) that tests target
- Umbrella `catalog.json` lists the plugin at version 1.0.2 matching the manifest
- Tests ✗ no helper test file (see Low)

## Positives
- Exec hygiene: absolute `/usr/bin/python3` with an explicit PATH-shadow rationale comment; `clearEnvironment: true` + whitelist env (PATH=/usr/bin:/bin, LC_ALL=C, HOME/XDG_RUNTIME_DIR nulled); argv arrays everywhere, zero `shell=True`; helper resolves tools via `shutil.which(name, path=SAFE_PATH)` and re-scrubs env (`SAFE_ENV`) for children; helper argv is entirely fixed strings — no untrusted data reaches argv; no secrets anywhere.
- Kill design is the strongest in the catalog: probe calls `os.setsid()` becoming a group leader, helpers inherit its group (no `start_new_session`), QML watchdog fires `kill -KILL -- -<pid>` (killpg) plus `signal(9)` — the negative-PID target only exists if setsid succeeded, so the fallback can't hit the shell's own group. Helper-side `SIGALRM` + `os._exit(124)` backstop for standalone runs.
- `_run()` is genuinely careful: per-call 2s deadline, 256 KiB producer cap returning `None` on overflow, non-blocking `select()` drain after child exit so a descendant holding the pipe can't stall past the deadline, SIGTERM→SIGKILL reaping in `finally`.
- Untrusted data: every device-controlled string (USB product/manufacturer, BT name/MAC, ifname, IP, lsblk model/mount) passes `_clip` (64 chars; mounts 128, capped 16); lists bounded by `MAX_ITEMS=64` on both producer and consumer (`slice(0, 64)`); every dynamic `Text` binding in Panel.qml is `textFormat: Text.PlainText` — verified all ~16 sinks; `JSON.parse` in try/catch behind a 300 KB consumer cap.
- Helper↔panel contract verified both directions: panel reads `ok` + `usb`/`bluetooth`/`network`/`storage`; item keys all emitted (extra keys `id`/`category`/`mac`/`size` unused, harmless). Missing tools (`_tool`→None), bad JSON (`except ValueError`), empty output, and `data.ok` falsy all degrade to empty sections or retained stale data — no crash path.
- Theme-clean: `qs.Commons` `Color`/`Style`/`Qt.rgba`-derived colors only, zero hardcoded hex (grep-verified); `moduleName`/`ipcTarget` match the manifest id.
- Read-only probe: the only filesystem access is sysfs reads under `/sys/bus/usb/devices`; no writes, no network surface at all.
