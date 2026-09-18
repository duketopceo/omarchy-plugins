# Bumblebee

Supply-chain exposure radar for the Omarchy bar. Periodically scans installed
packages, lockfiles, extension manifests, and MCP configs against a catalog of
known-compromised components — and shows the count before you find out the hard way.

Wraps [perplexityai/bumblebee](https://github.com/perplexityai/bumblebee)
(Apache-2.0). This plugin is integration glue — it does not vendor or modify the
upstream tool.

## Install

1. Install the `bumblebee` binary from the upstream
   [releases](https://github.com/perplexityai/bumblebee/releases) — pick the
   `linux_amd64` or `linux_arm64` tarball and place `bumblebee` on your PATH
   (e.g. `~/.local/bin`).
2. Then:

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-bumblebee
omarchy plugin enable io.github.duketopceo.bumblebee
```

## Features

- Bar shield turns urgent and the dropdown lists each exposure when a scanned
  component matches the catalog
- Background scans run on a stale-cache refresh: the helper re-scans at most
  every 6 hours (`BUMBLEBEE_SCAN_INTERVAL_S` to override) and serves cached
  results between runs — no daemon, no shipped systemd units
- An always-on `service` component (kept loaded by the shell) checks the
  cache age once an hour and force-rescans when it's stale — the radar stays
  fresh even if you never open the panel
- When a scan finds **new** exposures that weren't in the previous baseline,
  the service raises an urgent toast in the top-right corner (~10s, click to
  dismiss, max 3 stacked). The toast only fires on the *delta*: the first
  poll baselines silently, and zero exposures is always silent
- Partial scans surface a `PARTIAL` chip instead of silently undercounting
- Results cache at `~/.local/state/omarchy/bumblebee/last-scan.json` (0600,
  atomic writes)

## Exposure catalog

Upstream bumblebee ships no threat intel — matching requires an operator-supplied
catalog. This plugin ships a small starter set at `catalog/exposures.json`
(well-known incidents: the Sept-2025 `chalk`/`debug` npm compromise,
`event-stream`, `ua-parser-js`, `node-ipc`, `ctx`, `xz`).

Drop additional advisories as `*.json` files in
`~/.config/omarchy/plugins-data/bumblebee/catalog.d/` — they are merged at scan
time. Catalog updates to the shipped set ride plugin updates; nothing is fetched
at runtime unless you ask for it.

### Advisory refresh (opt-in)

Upstream releases ship a `threat_intel/` directory of advisories (~1000
entries). The **Refresh** button in the panel's Catalog tab — or
`bin/refresh_catalog.py` directly — downloads the **pinned** release tarball
(`perplexityai/bumblebee` tag `v0.1.2`, HTTPS only, ~64MiB cap), extracts
only `threat_intel/*.json` (path-traversal/symlink/non-regular members
rejected), validates each entry against the 0.1.0 catalog schema, and merges
them atomically to `catalog.d/upstream.json` (0600). It runs only when
invoked — never on a timer, never during status polls — and any failure
leaves `catalog.d` untouched. The Catalog tab shows "upstream refreshed Xd
ago" so staleness is visible instead of silent.

## Privacy & security posture

- Read-only scanning: bumblebee never executes package managers and never reads
  source files; MCP `env` values (which can hold secrets) are not emitted.
- The helper runs with a scrubbed environment, fixed tool paths, bounded output,
  and hard deadlines; cache files are owner-verified, descriptor-relative, 0600.
- No telemetry. The only network call is the opt-in catalog refresh (pinned
  repo+tag, HTTPS); everything else is local.

## External dependencies

See [UPSTREAM.md](UPSTREAM.md) for the upstream tool repo, license, and
per-architecture install commands.

- `bumblebee` binary (upstream releases; both amd64 and arm64 published)

## Remove

```bash
omarchy plugin disable io.github.duketopceo.bumblebee
omarchy plugin remove io.github.duketopceo.bumblebee
rm -rf ~/.local/state/omarchy/bumblebee ~/.config/omarchy/plugins-data/bumblebee
```

MIT — see [LICENSE](LICENSE). Upstream: Apache-2.0 (Perplexity).
