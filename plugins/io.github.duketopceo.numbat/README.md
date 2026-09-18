# Numbat

AI-agent activity radar for the Omarchy bar. Ambient visibility into what your
coding agents (Devin, Cursor, Claude Code, etc.) are actually doing on this
machine — live agent list, 24h findings count, and a findings feed.

Wraps [perplexityai/numbat](https://github.com/perplexityai/numbat)
(Apache-2.0). This plugin is a read-only consumer — it never installs hooks,
never writes to `~/.numbat/`, and never enables enforce mode.

## Install

1. Install the `numbat` binary from the upstream
   [releases](https://github.com/perplexityai/numbat/releases) — pick
   `linux_amd64` or `linux_arm64` and place `numbat` on your PATH
   (e.g. `~/.local/bin`).

   **Arch users:** the AUR package named `numbat` is an *unrelated* units-of-measure
   language. Do not `yay -S numbat` — use the GitHub release tarball.

2. Install agent hooks (one-time, your call — the plugin does not do this for you):

```bash
numbat hook install --agent all --emit all
```

`--emit all` is the recommended install: hooks stream live events **and**
findings to `~/.numbat/records.ndjson`, so the panel's Log tab shows a
STREAMED feed instead of 10-minute-old scan data. It is still monitor mode —
numbat observes and records, it never blocks or enforces. Plain
`numbat hook install --agent all` works too (findings-only hooks writing
`~/.numbat/findings.ndjson`); the Log tab then shows SCANNED.

3. Then:

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-numbat
omarchy plugin enable io.github.duketopceo.numbat
```

## Features

- Bar radar glyph shows live state; urgent tint when findings land in the last 24h
- Dropdown: findings feed (rule, agent, relative time) + per-agent last-activity
- **Findings toasts**: a persistent shell service stats the record files every
  5s; when they grow it diffs findings against a persisted watermark and raises
  a severity-tinted popup (max 3, ~8s each, click to dismiss) — even with the
  dropdown closed. First launch baselines silently; no popup storms
- Live event stream: `~/.numbat/records.ndjson` (`--emit all` hooks) is tailed
  every poll and takes precedence over the scan-cached feed — the Log tab marks
  the source STREAMED or SCANNED
- Graceful setup pane when numbat or its hooks aren't installed yet — no dead calls
- Reads `~/.numbat/findings.ndjson` and `~/.numbat/records.ndjson` live via
  bounded 256KiB tails, and runs `numbat scan --emit all` on a 10-min
  stale-cache cycle for the events backfill
  (summary cached at 0600 under `~/.local/state/omarchy/numbat/`)

## Where state lives

- `~/.numbat/findings.ndjson`, `~/.numbat/records.ndjson` — upstream record
  sinks, read-only for this plugin (either may be absent until hooks fire)
- `~/.local/state/omarchy/numbat/scan-cache.json` — parsed scan summary,
  atomic 0600 writes, 10-min freshness
- `lastSeenFinding` on this plugin's entry in `~/.config/omarchy/shell.json` —
  the toast watermark; written through the host's scoped `updateEntryInline`,
  so it survives shell restarts without letting old findings re-alert

## Privacy & security posture

- The plugin only reads records numbat already produces (`findings.ndjson`
  and `records.ndjson` tails, `numbat scan`, `numbat hook status`); it adds
  no new collection and never writes under `~/.numbat`
- `~/.numbat` data is treated as untrusted input: descriptor-relative opens,
  `O_NOFOLLOW`, owner + regular-file checks, control-char normalization
- Monitor-only by contract — shipped upstream rules are observe-only and this
  plugin cannot flip enforce mode
- No telemetry, no network calls from the plugin itself

## External dependencies

See [UPSTREAM.md](UPSTREAM.md) for the upstream tool repo, license, and
per-architecture install commands.

- `numbat` binary (upstream releases; amd64 + arm64)
- `numbat hook install` run by you for event collection (optional — without it
  the panel shows a setup hint)

## Remove

```bash
omarchy plugin disable io.github.duketopceo.numbat
omarchy plugin remove io.github.duketopceo.numbat
```

`~/.numbat/` is upstream's data dir — remove it separately if you also uninstall numbat.

MIT — see [LICENSE](LICENSE). Upstream: Apache-2.0 (Perplexity).
