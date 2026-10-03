# Plugin scorecard

The scorecard makes "11/10" a checkable artifact (plan R1, R2; KTD3). A surviving
plugin is 11/10 only when every criterion below passes and the dated manual
items are recorded. `scripts/check-scorecard.py` enforces it.

## Where things live

- This file owns the criteria, per-plugin idle spawn budgets, the `retiring`
  list and per-plugin waivers (the `scorecard-config` block below).
- Each surviving plugin's `docs/reviews/<id>.md` ends with a fenced
  `scorecard` block (JSON, stdlib-parsable) holding its status.

## Criteria (KTD3)

Static criteria, each `pass | fail | pending`:

| Key | Meaning |
|---|---|
| `no_open_hm_findings` | no open High or Medium review findings |
| `plaintext_external_text` | `Text.PlainText` on all external text |
| `exec_discipline` | every exec is deadline-paired with group kill and minimal env |
| `envelope` | helpers emit the R13 envelope (`ok`, `error`, `data`, `capabilities`) |
| `fixture_tests` | tests pass on the fixture corpus for every relevant hardware profile |
| `visibility_gating` | polling stops while the surface is not visible; one refresh on reveal |
| `stale_backoff` | stale labelling after 3 intervals; failing helper backs off to 1 try/60 s |
| `readme_claims` | README claims match working features |

Dated manual items:

| Key | Shape | Meaning |
|---|---|---|
| `spawn_measurement` | `{"value": <spawns/min>, "date": "YYYY-MM-DD"}` | idle panel-closed measurement; `value` must not exceed the plugin's budget |
| `asahi_pass` | `{"date": "YYYY-MM-DD"}` | live pass on the Asahi M1 Max bar |
| `x86_64_pass` | `{"date": "YYYY-MM-DD"}` | pass on an x86_64 machine (Dell); may be waived |

## Status semantics

- `pending`: not yet assessed, or not yet met. This is the initial state of
  every criterion. The default-mode gate passes on `pending`; `--release`
  fails on it.
- `fail`: a regression of something that previously passed (or a recorded
  measurement over budget). Fails in every mode.
- `pass`: checked, with evidence. Never claim `pass` without checking. Where
  cheap the checker cross-checks: `pass` on `plaintext_external_text` or
  `exec_discipline` fails if `scripts/check-plugin-contract.py` reports an
  error-severity finding for that plugin.
- A manual item with no date is `pending`. `x86_64_pass` listed under a
  plugin's waivers counts as satisfied.
- Every id in `catalog.json` needs a scorecard unless it is in `retiring`.
  A plugin directory without a scorecard fails. A `retiring` id still in
  `catalog.json` fails `--release` (incomplete retirement; U9 removes them).

## Idle spawn budgets

R6: estate total at most 10 spawns/min with every panel closed and the machine
idle. Per-plugin budgets (sum 5/min leaves headroom for omarchy-argus; `estate_budget` is enforced against the recorded total):

- fan 1 (daemon/helper tick), power 1 (headless service sampler), nexus 0,
  standby 0, bumblebee 1, numbat 1, pplx 0.5, neo 0.5.

Adjust a budget only with a written reason added here.

## Configuration

```scorecard-config
{
  "budgets": {
    "lukedaduke.fan": 1,
    "lukedaduke.power": 1,
    "lukedaduke.nexus": 0,
    "lukedaduke.standby": 0,
    "io.github.duketopceo.bumblebee": 1,
    "io.github.duketopceo.numbat": 1,
    "io.github.duketopceo.pplx": 0.5,
    "io.github.duketopceo.neo": 0.5
  },
  "estate_budget": 10,
  "retiring": ["lukedaduke.connections", "lukedaduke.ticker", "lukedaduke.agents"],
  "waivers": {
    "io.github.duketopceo.neo": {
      "x86_64_pass": "local-only plugin, excluded from publishing; no x86_64 hardware target"
    }
  }
}
```
