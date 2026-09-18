# Upstream dependency: bumblebee

This plugin is a thin Omarchy shell wrapper around Perplexity's
**bumblebee** CLI. It does not vendor, bundle, or reimplement bumblebee —
it runs the tool, reads its scan output, and renders it.

| | |
|---|---|
| Tool | `bumblebee` — supply-chain exposure scanner |
| Repository | https://github.com/perplexityai/bumblebee |
| License | Apache-2.0 (upstream) |
| Plugin repo | https://github.com/duketopceo/omarchy-bumblebee |

## What the tool does vs. what the plugin does

- **bumblebee** scans a host's roots against a compromise/exposure catalog
  (`baseline`, `roots`, `selftest`, `version`). Its release tarballs ship a
  `threat_intel/` directory of advisory records.
- **This plugin** merges a bundled starter catalog with your
  `catalog.d/*.json`, runs `bumblebee baseline` on a slow cadence (or on
  demand), keeps a scan log, renders exposures in the bar dropdown, and
  raises a toast only when *new* exposures appear.

The optional **Refresh advisories** action downloads the pinned upstream
release tarball over HTTPS and merges its `threat_intel/` records into
`catalog.d/upstream.json`. It is strictly opt-in (button or CLI), validates
each record against the catalog `0.1.0` schema, and never runs during
status polls. The pin (repo + tag + HTTPS) is the integrity story — there
is no upstream signature infrastructure.

## Install the tool

Download a release tarball for your architecture and place `bumblebee` on
your `PATH` (e.g. `~/.local/bin`):

```bash
# x86_64
curl -L https://github.com/perplexityai/bumblebee/releases/latest/download/bumblebee-linux-x86_64.tar.gz | tar xz -C ~/.local/bin bumblebee

# aarch64 (Omarchy ARM / Asahi)
curl -L https://github.com/perplexityai/bumblebee/releases/latest/download/bumblebee-linux-aarch64.tar.gz | tar xz -C ~/.local/bin bumblebee
```

Asset names vary by release — check the release page if the exact name
differs: https://github.com/perplexityai/bumblebee/releases

Verify with `bumblebee version`.
