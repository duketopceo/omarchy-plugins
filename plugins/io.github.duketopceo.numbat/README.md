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
numbat hook install --agent all
```

3. Then:

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-numbat
omarchy plugin enable io.github.duketopceo.numbat
```

## Features

- Bar radar glyph shows live state; urgent tint when findings land in the last 24h
- Dropdown: findings feed (rule, agent, relative time) + per-agent last-activity
- Graceful setup pane when numbat or its hooks aren't installed yet — no dead calls
- Reads `~/.numbat/records.ndjson` via a bounded 256KiB tail — safe on huge files

## Privacy & security posture

- The plugin only reads records numbat already wrote; it adds no new collection
- `~/.numbat` data is treated as untrusted input: descriptor-relative opens,
  `O_NOFOLLOW`, owner + regular-file checks, control-char normalization
- Monitor-only by contract — shipped upstream rules are observe-only and this
  plugin cannot flip enforce mode
- No telemetry, no network calls from the plugin itself

## External dependencies

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
