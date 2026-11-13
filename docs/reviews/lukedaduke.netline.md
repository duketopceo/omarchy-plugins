# Review: lukedaduke.netline (omarchy-netline)

Reviewed: 2877fbc · 2026-11-13 · verdict: SHIP-WITH-FIXES

## Findings

### Medium
- [MED] bin/status.py — no `signal.alarm` backstop. The panel arms a 12s SIGKILL deadline (Panel.qml:144), so a wedged helper is killed rather than left running, but the helper itself has no self-limit. `[helper-alarm]`.

### Low
- [LOW] Panel.qml:81,100,110,120 — four raw `Process` blocks instead of `lib/DeadlineProcess`, so there is no process-group kill and no default-on `ProcEnv`. Each already sets `clearEnvironment: true` and an explicit `environment`, so the exposure is the group-kill path only. `[raw-process]`.
- [LOW] bin/netline-gui.py:155 — no `signal.alarm`; the GUI server is expected to run forever, so the finding is advisory rather than a defect. The prune path is bounded by SQL.
- [LOW] bin/netline.py:662 — collector has no alarm; it is a long-lived daemon, so a per-iteration bound matters more than a process bound. Not currently enforced.

### Info
- [INFO] Strings from the packet path (`comm`, hostname, flag reason) now clip at 120 chars in `status.py`. The payload measures ~1.7 KB with 20 flags; the panel has no byte cap on its `StdioCollector`, so the helper-side clip is the only bound.
- [INFO] `bin/agents-auth.py` ships with the plugin but is not exercised by any panel path. It exists for the operator's own agent-auth checks.
- [INFO] Two HTML views share one `/api/data` payload. The hex map reads `stats`; changing that key blanks its header without an error.

## Marketplace readiness
- manifest.json: ✓ (id `lukedaduke.netline`, kinds `bar-widget`, `entryPoints.barWidget` → `Panel.qml`, version/license/description set)
- README.md: ✓ (install, requirements including the required sysctl, layout, data handling)
- AGENTS.md: ✓ (failure mode, layout exception, privilege split)
- LICENSE: ✓ (MIT)
- preview.png: ✗ (not generated)
- Tests: ✓ (`tests/test_netline_status.py` — payload shape, missing store, clip bound, human format)
- systemd: ✓ (collector, GUI, prune timer)
- sysctl: ✓ (drop-in ships with the plugin)

## Positives
- All 16 dynamic `Text` sinks set `textFormat: Text.PlainText`.
- Every `Process` uses an absolute interpreter path (`/usr/bin/python3`), argv-only invocation, `clearEnvironment: true`, and a minimal explicit env.
- The GUI opens the store `mode=ro`; only the root collector writes.
- Collector failure is bounded: three restart attempts in 120s, then it stops rather than looping.
- The required sysctl is documented in README, AGENTS.md, the unit file, and shipped as a drop-in — this was the failure that cost a debugging session.
- Both maps verified in a real browser against a live payload, including the flag colouring and stat header.

## Scorecard

See docs/SCORECARD.md for semantics.

```scorecard
{
  "plugin": "lukedaduke.netline",
  "criteria": {
    "no_open_hm_findings": "pending",
    "plaintext_external_text": "pending",
    "exec_discipline": "pending",
    "envelope": "pending",
    "fixture_tests": "pass",
    "visibility_gating": "pass",
    "stale_backoff": "pass",
    "readme_claims": "pending"
  },
  "manual": {
    "spawn_measurement": {
      "value": null,
      "date": null
    },
    "asahi_pass": {
      "date": null
    },
    "x86_64_pass": {
      "date": null
    }
  },
  "notes": "Initial review 2026-11-13. plaintext_external_text is pending, not failing: all 16 Text sinks set PlainText, but check-scorecard runs the contract scan in strict_estate mode where any error invalidates a claimed pass, and netline still has four raw-process and four helper-alarm findings. Marking it pass would be overclaiming. fixture_tests passes after adding tests/test_netline_status.py. visibility_gating passes: statusTimer binds to VisibilityGate. exec_discipline stays pending on the four raw Process blocks, which need shared/qml/DeadlineProcess vendored into lib/ first."
}
```
