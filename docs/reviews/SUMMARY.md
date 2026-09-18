# JEV Review Summary — All Marketplace Plugins

Reviewed 2026-09-18 · 10 plugins · report-only pass (no code changed)
Per-repo reports: `docs/reviews/<plugin-id>.md`

## Scoreboard

| Plugin | Ver | Verdict | C | H | M | L | I |
|--------|-----|---------|---|---|---|---|---|
| lukedaduke.agents | 1.1.0 | **NEEDS-WORK** | 0 | 2 | 4 | 4 | 7 |
| lukedaduke.standby | 1.0.3 | SHIP-WITH-FIXES | 0 | 1 | 1 | 7 | 7 |
| lukedaduke.fan | 2.1.4 | SHIP-WITH-FIXES | 0 | 1 | 2 | 4 | 5 |
| io.github.duketopceo.bumblebee | 0.2.0 | SHIP-WITH-FIXES | 0 | 0 | 2 | 4 | 8 |
| lukedaduke.connections | 1.0.0 | SHIP-WITH-FIXES | 0 | 0 | 3 | 2 | 4 |
| lukedaduke.nexus | 1.0.2 | SHIP-WITH-FIXES | 0 | 0 | 2 | 5 | 7 |
| lukedaduke.power | 1.1.2 | SHIP-WITH-FIXES | 0 | 0 | 2 | 3 | 5 |
| io.github.duketopceo.numbat | 0.2.0 | SHIP-WITH-FIXES | 0 | 0 | 1 | 4 | 5 |
| lukedaduke.ticker | 2.1.4 | **SHIP** | 0 | 0 | 0 | 5 | 4 |
| io.github.duketopceo.pplx | 0.2.0 | **SHIP** | 0 | 0 | 0 | 4 | 10 |
| **Totals** | | | **0** | **4** | **19** | **42** | **62** |

## The four Highs

1. **agents — rich-text injection on untrusted sync data.** Zero `Text.PlainText`
   anywhere; the sync feature ingests JSON written by *other machines* and renders
   `providerName`/status text under `Text.AutoText`. Crafted markup (including
   `<img>` → silent remote fetch) reaches the shell UI. Security-relevant.
2. **agents — dead `fireworks` provider.** `providerEnabled()` allowlist omits
   `fireworks` even though the manifest description, defaults, and panel wiring
   advertise it; also silently default-enables providers absent from manifest
   defaults. Code/manifest drift in both directions.
3. **standby — caffeine toggle permanently broken.** State reads the marker
   file's *content*; `toggleCaffeine` only `touch()`es it (0 bytes) → always
   false, UI stuck "off", idle daemon inhibited forever → **no auto-lock/blank**.
4. **fan — fan mode never displays.** `Panel.qml` scrubs `XDG_RUNTIME_DIR` from
   the collector env → helper reads `~/.local/run/...` while the daemon writes
   `/run/user/<uid>/...` → `fan_mode` always `"auto"`; badge, presets, and
   right-click cycling are dead UI.

## Recurring patterns (fix once, apply everywhere)

- **Deadline/watchdog mismatches** — numbat (14s kill vs ~30s helper worst case),
  nexus (5s kill vs ~6s worst case), connections-adjacent patterns. Slow-but-healthy
  runs get killed and discarded. Audit every `killTimeout`/`SIGALRM` pair against
  the helper's real worst case.
- **Dead advertised features** — agents fireworks, fan daemon (ships as dead code,
  no systemd unit/installer), connections `dimmed` bindings + mis-anchored popups,
  bumblebee `BUMBLEBEE_SCAN_INTERVAL_S` knob scrubbed away by its own env hygiene.
- **Silent failures** — helper stderr never collected (ticker, standby), `{"error"}`
  payloads emitted but never read (standby, bumblebee age path), missing helper
  binaries degrade to empty widgets (agents).
- **Env scrubbing side effects** — the hardened env pattern breaks legitimate
  consumers twice: fan's `XDG_RUNTIME_DIR`, bumblebee's documented interval knob.
- **Missing test coverage** — agents, power, nexus have no dedicated test files
  (new-gen trio all ship real suites; ticker has one).
- **PlainText** — new gen: 100% coverage (74/74 verified). Old gen: good except
  agents (zero — the only real injection surface found).

## Generation gap confirmed

The hardened `io.github.duketopceo.*` trio graded best overall: pplx is the only
plugin with **zero Medium-or-above** findings; numbat/bumblebee's only Mediums are
single liveness/correctness defects, not vulnerabilities. Their security posture
(descriptor-relative `O_NOFOLLOW` I/O, atomic 0600 publishes, scrubbed env,
group-kill deadlines, tar sanitization) held up under review.

The older `lukedaduke.*` gen is security-decent in helpers (argv-only exec,
absolute paths, byte budgets are common) but ships more functional dead code and
has the review's only injection-class finding (agents rich-text).

## Recommended remediation order

1. **agents** — unverified listing, widest usage (271 views/22 installs), both a
   security High and a correctness High. PlainText sweep + fireworks allowlist +
   provider/manifest reconciliation.
2. **standby** — caffeine High is a user-facing breakage with a security-relevant
   side effect (idle lock inhibited). One-line fix class (existence, not content).
3. **fan** — keep `XDG_RUNTIME_DIR` in `procEnv`; either wire or drop the daemon.
   35 installs — highest blast radius of the verified set.
4. **bumblebee** — watermark clobber (helper emits cached error → age path skips
   diffing) + redirect re-check on the HTTPS gate.
5. **numbat** — raise QML deadlines ≥32s or lower `SCAN_TIMEOUT_S`.
6. **connections** — unverified; dead bindings, popup anchoring, IPC duplicate
   caveat. Cheap fixes, then re-submit for verification.
7. **nexus / power** — `tran=="usb"` gate, deadline fix, malformed-history guard,
   add the missing test files.
8. **Lows/info sweep** — stderr collectors, `.error` reads, README gap fills
   (ticker removal/deps sections).

## Notes

- `connections` was reviewed once; its findings inform both the unverified-pair
  and older-gen buckets (no duplicate report).
- Standalone clones were not modified. Umbrella copies were verified
  byte-identical where checked (ticker, nexus, standby, bumblebee, pplx, power);
  fan's umbrella copy has **diverged** (pkexec daemon-start, DeviceTree CPU
  detection) — reconcile before the next fan publish.
- pytest isn't installed system-wide; reviewers used `uvx --with pytest` or
  static review. Umbrella suite status: 125 tests green as of v0.2.0 work.
