# Review: io.github.duketopceo.pplx (omarchy-pplx)
Reviewed: b85240f · 2026-09-18 · verdict: SHIP

## Findings

### Low
- [LOW] Panel.qml:156,163 — `openHit`/`copyHit` gate on `/^https?:\/\//`, so plain `http://` result URLs reach `xdg-open`/`wl-copy`. The gate does its security job (blocks `file:`/`javascript:`/`data:`), and http results are legitimate for a search UI — but the rubric bar is https-only; either tighten to `https:` or document the deliberate trade-off.
- [LOW] Panel.qml:185-191 + 269-272 — closing the panel mid-search calls `killSearch()`; the killed process's `onStreamFinished` then fires with empty text and sets `lastError = "no output from helper"`, so a user-initiated cancel resurfaces as an error banner on the next open (`hasSearched`/`lastError` are not reset in `onOpenedChanged`). Clear `lastError` when the close path kills the search.
- [LOW] Panel.qml:212 — if the status helper dies before emitting (crash, missing `/usr/bin/python3`), the empty-stdout early return skips `root.statusKnown = true`, so the pill sits at pulsing "CHECKING" forever rather than an error state (30s repolls keep hitting the same wall). Set `statusKnown` (or a probe-error state) on the empty-output path.
- [LOW] bin/pplx_status.py:258-279 + Panel.qml:169-175 — history delete resolves the visible index against a fresh read of the journal: a `_record_history` prepend landing between render and click shifts every index, so the wrong row is deleted; the read-modify-write can likewise lose the racing insert. Narrow window and self-healing (the emit carries the fresh list), but consider tagging deletes with the entry's `at`+`query` or serializing journal mutations.

### Info
- [INFO] bin/pplx_search.py:319-322, bin/pplx_status.py:303-306 — `_resolve_key` takes the first non-empty stdout line of `omaseal get` verbatim as the credential; if omaseal ever prepends a warning/diagnostic, that line is injected into pplx's env (fails safe to `needs_key`, but worth pinning the contract).
- [INFO] bin/pplx_search.py:160-168, bin/pplx_status.py:139-147 — the byte cap is checked after `buf += chunk`, so a stream can exceed its cap by one 64KB read; and a child that floods stdout then blocks on the full pipe is reported as `timeout` rather than `overflow` (`_result_from_run` checks timeout first). Bounded either way — label accuracy only.
- [INFO] bin/pplx_status.py:187 — `_read_capped` uses a single `os.read(fd, limit)`; a short read on an unusual filesystem yields truncated JSON → journal treated as corrupt → empty history. Loop-until-EOF would close it.
- [INFO] bin/pplx_status.py:215-219 — `_history_entry` clips `query`/`at` by length but does not control-char-normalize them (unlike `_record_history`, which `_clean`s at write time); a foreign-written journal could carry control chars into the panel. `Text.PlainText` + elide mitigate — defense-in-depth only.
- [INFO] Panel.qml:202-303 — none of the three `Process` objects collect stderr, so a Python traceback in a helper is invisible (panel only sees "no output from helper"). Fine for production; a stderr collector would aid field debugging.
- [INFO] bin/pplx_search.py:14-15 — by design the helper never consults pplx's own `~/.config` credentials (`pplx auth login` is TTY-only): a user who authed the upstream CLI directly still gets `needs_key` → NO KEY. Documented scope; noted so the setup-pane copy stays honest.
- [INFO] Panel.qml:97-104 — `procEnv` drops `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS`; `omaseal` still reaches the session bus via godbus's `/run/user/<uid>` fallback on systemd (verified against OmaSeal's godbus v5.2.2), so Omarchy is unaffected — but a dbus-launch-style session would silently resolve to NO KEY.
- [INFO] repo — no `.gitignore`; `bin/__pycache__/` exists untracked and could be committed accidentally. Marketplace-hygiene nit.
- [INFO] manifest.json — `version: "0.2.0"` but the repo has no git tags; tagging the release would keep the marketplace listing auditable.

## Marketplace readiness
- manifest.json ✓ — schemaVersion 1, id matches repo/dir, `kinds: [bar-widget]`, `entryPoints.barWidget` → Panel.qml present, complete `barWidget` block (displayName/category/allowMultiple/defaultSection), `activation: on-demand` accurate (no network at idle; status probe is exec-only)
- README.md ✓ — install (`omarchy plugin add`/enable), remove (disable/remove), external deps (pplx release tarballs per-arch, BYOK key, optional omaseal + wl-copy), feature/flag mapping, security posture — matches the implementation
- LICENSE ✓ — MIT
- preview.png ✓ — 1280×720 PNG
- UPSTREAM.md ✓ (bonus) — upstream provenance, Apache-2.0 license split, per-arch install commands, verify command
- Tests ✓ — omarchy-plugins/tests/test_pplx.py: 44 cases covering secret-never-on-argv/emitted, omaseal resolution order, hit compaction/clipping/cap, AUTHENTICATION→needs_key, metachar/leading-dash argv safety, journal append/clip/cap/corruption/failure-isolation, flag allowlist + `--limit` clamping, `--delete` index validation, real `_run` group-kill and byte-cap, plus structural panel greps (https gate, chip wiring, zero hex colors)

## Positives
- No shell anywhere: every exec is an argv array with fixed absolute binaries (`/usr/bin/python3`, `/usr/bin/kill`, `/usr/bin/xdg-open`, `/usr/bin/wl-copy`); tool resolution uses a fixed literal TOOL_PATH (`~/.local/bin` + system dirs), never the inherited PATH
- Secret hygiene is airtight: the API key enters the child only via `extra_env` merge — never argv/stdout/logs — and `_redact` scrubs it even out of API-controlled hit fields and error messages; `_extract_error` returns only structured `{code,message}` fields, so raw stderr can never echo env into the panel
- Option-chip defense in depth: panel emits `--recency/--context/--limit` pairs, helper re-validates every value against frozensets/int-range and drops anything else; literal `--` on both sides means untrusted query text can never become a pplx flag (leading-dash case is tested)
- Layered deadlines that actually add up: omaseal 2s + pplx 12s < SIGALRM 15s < QML watchdog 17s; status 5s alarm < 8s watchdog; selectors-based drains with per-stream byte caps; `start_new_session` + `os.setsid` + SIGTERM→SIGKILL `killpg`, and the panel's group-kill (`kill -KILL -- -pid`) plus `proc.signal(9)` covers a failed setsid
- File I/O is the full standby pattern: dirfd-relative `O_NOFOLLOW` opens, euid + regular-file + size checks, `O_EXCL` same-dir temp + `os.replace` at 0600; the journal is best-effort (a write failure can never alter the stdout contract) and every read tolerates missing/corrupt/oversized input
- Untrusted data is bounded end-to-end: control-char normalization, whitespace collapse, per-field clips (title/snippet 200, url 400, domain 128, date 64), hits capped at 8; all 24 QML `Text` elements are `Text.PlainText` (grep-verified, and a test enforces it); QML-side JSON parse guards + 300KB ceiling + array slicing
- Contract fit is exact: every emitted key (`ok/needs_key/installed/hits/error/elapsed_ms`, `installed/authed/copy_available/history`, `ok/history/error`) is consumed; `AUTHENTICATION`→`needs_key` matches the real upstream error codes; delete emits the fresh list so the panel self-heals on any error path; history re-polls on tab open and after each successful search
- Honest UX states: CHECKING / NOT INSTALLED / NO KEY / READY plus guided setup panes, copy button hidden when `wl-copy` is absent, elapsed-ms and hit-count reporting, brand attribution footer
- Real-world verified: journal exists at `~/.local/state/omarchy/pplx/history.json` at mode 0600 with well-formed entries from live searches
