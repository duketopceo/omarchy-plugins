# External plugin contract follow-up

Snapshot date: 2026-09-23.

The shared checker was run read-only against the enabled external checkout set.
This is a handoff summary, not a claim that third-party source is owned here.
Raw findings are intentionally not committed because they can contain local
paths or user-specific values.

## Summary

- Enabled external/local surfaces scanned: **17**
- Contract findings: **654**
- Errors: **586**
- Warnings: **68**
- Owned umbrella plugins are clean of contract errors; see
  `docs/PLUGIN_CONTRACT.md`.

## Findings by rule

| Rule | Count | Owner action |
|---|---:|---|
| PlainText coverage | 567 | Patch the owning QML checkout; prioritize remote/device/LLM text. |
| Timer budget review | 67 | Document one-shot/UI lifetime or reduce permanent polling. |
| Fixed executable path | 18 | Replace ambient interpreter/shell invocation in the owning helper. |
| Minimal environment | 1 | Remove inherited secret-bearing environment from the helper. |
| HTTPS-only network code | 1 | Replace the executable-code URL or document a safe boundary. |

## Highest-volume owners

| Owner/plugin | Findings | Follow-up |
|---|---:|---|
| `io.github.sirjul1337.lock-explorer` | 235 | Upstream review before any lock/PAM change. |
| `ssupt.audio-control` | 107 | Upstream QML/resource review; preserve basic audio fallback. |
| `io.github.duketopceo.dayflow` | 86 | Privacy/retention owner review before enabling capture changes. |
| `io.github.twiking.omasettings` | 49 | Separate configuration editing from plugin lifecycle ownership. |
| `tmn73.calendar` | 30 | Add stale-auth/network state and PlainText coverage upstream. |
| `mohamedmansour.finance` | 24 | Validate remote values and document egress. |
| `io.github.duketopceo.omaseal` | 19 | Confirm canonical keyring handoff and package metadata. |
| `robzolkos.github` | 19 | Bound API/rate-limit/error states upstream. |
| `nixfred.blip` | 18 | Make gateway/stale/privacy states explicit. |

The complete scan is reproducible with:

```sh
python3 scripts/check-plugin-contract.py --plugin-root <external-plugin-root> --format json
```

Record the owner, severity, proposed patch, and test evidence for each accepted
or rejected finding in this file. Do not paste raw JSON containing local paths
or credentials into the repository.
