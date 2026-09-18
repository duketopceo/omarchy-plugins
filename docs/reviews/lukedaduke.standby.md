# Review: lukedaduke.standby (omarchy-standby)

Reviewed: 28a27ad · 2026-09-17 · verdict: SHIP-WITH-FIXES

## Findings

### High
- [HIGH] Standby.qml:107-109 — caffeine state reads `text().length > 0` on the `stay-awake` marker file, but `toggleCaffeine` only ever creates it via `p.touch()` — a 0-byte file, so `root.caffeine` is permanently `false`: the UI always shows "off" and the unlink branch (Standby.qml:70-71) is unreachable, leaving the idle daemon inhibited forever (no auto-lock/blank) — set `root.caffeine = true` in `onLoaded` (existence, not content) and keep `onLoadFailed` → `false`.

### Medium
- [MEDIUM] Standby.qml:131,256 vs bin/standby-data:226,244 — helper emits `{"error": "unable to determine location"}` / `{"error": "weather fetch failed: ..."}`, but the panel never reads `.error`: JSON parses cleanly, `weatherError` stays `""`, and the weather column's `visible` gate (`temperature !== undefined || weatherError !== ""`) hides it silently instead of showing the failure — surface `weatherData.error` into `root.weatherError` after `JSON.parse`.

### Low
- [LOW] Standby.qml:117-137 — no `stderr` collector on `weatherProc`; a python traceback (malformed cache, TypeError paths below) surfaces only as "weather unavailable" with no diagnostics — add a `stderr: StdioCollector` and truncate/log it.
- [LOW] bin/standby-data:123 — `float(lat)`/`float(lon)` on a `weather.json` containing list/dict values raises `TypeError`, which `except (OSError, ValueError)` misses → traceback, empty stdout — catch `TypeError` (or validate with `isinstance((int,float))`) before converting.
- [LOW] bin/standby-data:247-276 — remote-JSON shape is assumed: `data.get` on a non-dict body, and `daily.get("sunrise",[None])[0]` on a non-list member, raise uncaught `AttributeError`/`KeyError`/`TypeError` → crash with no output — wrap the result-building block in try/except and fall back to `read_cache()`.
- [LOW] bin/standby-data:206-209 — `read_cache` accepts anything starting with `{`; a truncated/corrupt cache re-emits invalid JSON → panel shows "weather parse error" — `json.loads` the cache and re-serialize, or discard on failure.
- [LOW] bin/standby-data:191-209 — cache has no timestamp/TTL; on persistent outage the overlay shows arbitrarily stale weather with no staleness indicator — store a `fetched_at` and expire or annotate old cache.
- [LOW] Standby.qml:42-46 — `refreshWeather` restarts via `running=false; running=true`; if that doesn't kill an in-flight fetch the restart may be a no-op while the old proc holds the collector (bounded by the 20s deadline, so impact is limited) — prefer `weatherProc.signal(9)` before restarting.
- [LOW] README.md — no removal instructions or dependencies section (install shows `omarchy plugin add`/`enable`; nothing on `omarchy plugin remove` or the python3/network requirement) — add a Remove + Requirements block.

### Info
- [INFO] Standby.qml:173 — hardcoded `color: "black"` on the background Rectangle; intentional pure-black OLED backdrop rather than a theme color — acceptable, noted per rubric.
- [INFO] bin/standby-data:163 — when `weather.json` is absent the helper geolocates via `https://ipapi.co/json/`, disclosing the user IP to a third party; README documents only Open-Meteo — mention the fallback in README/Notes.
- [INFO] bin/standby-data:270 — `feelsLike` is emitted but never rendered — dead contract key, harmless.
- [INFO] Standby.qml:27-33 — `close()`/`toggle()` clear `opened` without calling `shell.hide`; if the shell tracks overlay visibility, a toggle-close could desync `summon` state — confirm shell contract or route through `dismiss()`.
- [INFO] Standby.qml:104 — `caffeineFile.path` concatenates `Quickshell.env("HOME")`; unset HOME yields a bogus `null/...` path (fails safe to `caffeine=false`) — cosmetic.
- [INFO] ROADMAP.md:7,13 — stale: claims preview.png is still missing / unchecked launch item, but a 1280×720 preview.png now ships.
- [INFO] tests/ — no `test_standby*.py` for `bin/standby-data` (WMO mapping, `iso_to_hm`, cache read/write, HTTPS/redirect gates, deadline); the manifest is covered only indirectly via `test_manifests.py`/`validate-manifests.py` — worth adding to match `test_ticker_stats.py`/`test_numbat.py` coverage.

## Marketplace readiness
- manifest.json ✓ (valid; id `lukedaduke.standby`, kinds `["overlay"]`, `entryPoints.overlay` → `Standby.qml` exists, `keepLoaded: true`, schemaVersion 1)
- README ✓ install/enable/usage/keys · ✗ removal · ✗ dependencies
- LICENSE ✓ MIT · preview.png ✓ 1280×720 PNG
- Helper `bin/standby-data` executable ✓ and byte-identical to the umbrella-repo copy (`plugins/lukedaduke.standby/`)

## Positives
- Exec hygiene: absolute `/usr/bin/python3` with an explicit PATH-shadow/hostile-HOME rationale comment; `clearEnvironment: true` + whitelist env (`PATH=/usr/bin:/bin`, `HOME`/`XDG_RUNTIME_DIR`/`LANG` nulled, `LC_ALL=C`); argv arrays everywhere, no shell — including the `execDetached` caffeine toggle.
- Network: HTTPS-only enforced twice — scheme gate in `fetch_json` (bin/standby-data:144) plus `HTTPSOnlyRedirectHandler` refusing downgrade redirects (:131-137); JSON Content-Type gate; 1 MiB producer-side byte budget with Content-Length pre-check and bounded read; 200 KB consumer-side cap (Standby.qml:126).
- File safety: `_open_dir` requires O_DIRECTORY+O_NOFOLLOW+same-uid, `_read_capped` adds O_NOFOLLOW+regular-file+size cap, `_publish` writes via O_EXCL temp + fsync + atomic rename at 0o600 — solid symlink/traversal posture for both the settings read and cache write.
- Deadline design: layered and correctly ordered — helper SIGALRM 18s < panel SIGKILL 20s; `onExited` disarms the deadline timer; SIGALRM backstop exits even if never reaped.
- Untrusted data: every `Text` item carries `textFormat: Text.PlainText` (15/15 grep-verified); remote strings bounded (location name capped at 60 chars); JSON.parse wrapped in try/catch; error/empty paths set a local status string.
- Overlay entry-point surface correct for the kind: `open/close/toggle/dismiss` functions, `PanelWindow` gated on `opened`, `WlrLayer.Overlay` + exclusive keyboard grab + Esc/Q/Space/click dismissal, `shell.hide(manifest.id)` on dismiss.
- Theme-clean: `qs.Commons` `Color.foreground`/`Color.urgent`, `Style.gapsOut`/`Style.font.*` throughout; zero hex literals (sole hardcoded color is the intentional `black` OLED backdrop).
