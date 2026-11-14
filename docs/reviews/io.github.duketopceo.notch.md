# Review: io.github.duketopceo.notch

Island surface v0.2.0 (2026-11-14). Assessed against `docs/SCORECARD.md` for the Asahi path; x86_64 manual pass still open (CI covers ubuntu-latest + arm runners for pytest).

```scorecard
{
  "plugin": "io.github.duketopceo.notch",
  "criteria": {
    "no_open_hm_findings": "pass",
    "plaintext_external_text": "pass",
    "exec_discipline": "pass",
    "envelope": "pass",
    "fixture_tests": "pass",
    "visibility_gating": "pass",
    "stale_backoff": "pass",
    "readme_claims": "pass"
  },
  "manual": {
    "spawn_measurement": {
      "value": null,
      "date": null
    },
    "asahi_pass": {
      "date": "2026-11-14"
    },
    "x86_64_pass": {
      "date": null
    }
  },
  "notes": "2026-11-14: Island entry + Commons.Color theme; fixture tests in tests/test_notch_*.py and test_island_activity.py; plaintext covered by island tests; README install URL corrected to omarchy-plugins. x86_64 interactive pass deferred (no local x86 host)."
}
```
