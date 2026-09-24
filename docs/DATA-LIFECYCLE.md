# Data and secret lifecycle

This document defines the active plugin estate's data boundaries. The
machine-readable source of truth is [`docs/data-lifecycle.json`](data-lifecycle.json);
validate it with:

```sh
python3 scripts/check-data-lifecycle.py
```

The policy is intentionally conservative: it describes what may be collected,
where it may leave the machine, how long it may remain, and how an operator
pauses, exports, or deletes it. It does not silently delete user data.

## Secrets

OmaSeal is the canonical secret-management surface. Consumers resolve a secret
at the moment they need it through the Secret Service API or an inherited,
non-persistent file-descriptor/stdin channel. The supported release path does
not place secret values in argv, environment variables, logs, QML state,
process metadata, or user-facing errors.

A locked, unavailable, or empty keyring is a setup state. Consumers show a
recovery action and do not fall back to plaintext. Existing compatibility
paths are not release-ready until their owner documents and removes the
fallback.

## Voice ownership

- **Default:** `hancore.voxtype-enhance` / `voxtype.service`.
- **Alternate:** `io.github.duketopceo.dim`, explicitly opt-in.
- **Concurrency:** only one voice owner may claim the microphone by default.
  Starting the alternate while the default is active must produce an explicit
  choice or refusal, not a silent second recorder.
- **Pause:** each owner exposes a pause/disable path and releases its device
  claim when stopped.

## Surface policy

| Surface | Purpose | Egress | Default retention | Controls |
|---|---|---|---|---|
| Screen capture / Dayflow | Time journal and optional summaries | Sampled frames only when summarization is enabled | 14 days or 2 GiB frames; 90 days or 1 GiB journal; 7 backups | Pause, purge, export, backup verification |
| Voice / Voxtype | Local dictation and transcription | Local model by default; model download only on selection | Session audio is not retained by this plugin; model files persist until cleared | Pause, clear models, user-selected output |
| Clipboard | Paste history | None unless a user action invokes an external consumer | 7 days or 1000 entries, subject to host policy | Pause, host delete/export |
| Messages / Blip | Read/send through the user-authorized Mac gateway | SSH/Tailscale to the configured Mac; no Linux message database | Opened attachments may be cached for 7 days | Pause, attachment-cache purge |
| Calendar | Events and reminders | Configured calendar provider | 7-day stale-event cache | Pause, provider delete, provider export |
| Finance | Watchlist values | Configured market-data provider | 24-hour display cache | Pause, local-cache cleanup |
| Weather | Current conditions and forecast | Configured weather provider | 1-hour stale cache | Pause, local-cache cleanup |

These are policy ceilings, not permission to collect more data. Operators may
choose lower budgets. A plugin that cannot enforce its declared pause/delete
behavior is degraded and must not be treated as the canonical owner.

## Deletion and migration

Deletion is always operator-confirmed and scoped to the named surface. A
migration may disable a collector or remove a UI, but it must not delete
frames, transcripts, message history, clipboard history, keyring entries, or
backups as a side effect. Backups are included in the surface's purge/export
report so a user can see what remains.

Third-party source changes are tracked in
`docs/reviews/active-plugin-contract.md`; this document records the contract,
not ownership of those repositories.
