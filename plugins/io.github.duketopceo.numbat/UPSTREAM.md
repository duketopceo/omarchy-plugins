# Upstream dependency: numbat

This plugin is a thin Omarchy shell wrapper around Perplexity's **numbat**
CLI. It does not vendor, bundle, or reimplement numbat — it reads the
state numbat produces and renders it.

| | |
|---|---|
| Tool | `numbat` — agentic activity monitor |
| Repository | https://github.com/perplexityai/numbat |
| License | Apache-2.0 (upstream) |
| Plugin repo | https://github.com/duketopceo/omarchy-numbat |

## What the tool does vs. what the plugin does

- **numbat** installs agent-native observe-only hooks, records findings and
  events to `~/.numbat/`, and provides `scan`, `hook`, and `agents`
  subcommands.
- **This plugin** tails those record files read-only, summarizes them for a
  bar widget, watches for new findings in a low-load shell service, and
  raises a toast when something new lands. It never runs `hook install`,
  never enforces policy, and never modifies agent configuration.

## Install the tool

Download a release tarball for your architecture and place `numbat` on
your `PATH` (e.g. `~/.local/bin`):

```bash
# x86_64
curl -L https://github.com/perplexityai/numbat/releases/latest/download/numbat-linux-x86_64.tar.gz | tar xz -C ~/.local/bin numbat

# aarch64 (Omarchy ARM / Asahi)
curl -L https://github.com/perplexityai/numbat/releases/latest/download/numbat-linux-aarch64.tar.gz | tar xz -C ~/.local/bin numbat
```

Asset names vary by release — check the release page if the exact name
differs: https://github.com/perplexityai/numbat/releases

> AUR note: the `numbat` package in the AUR is the *numbat units language*,
> not this tool. Install from the GitHub releases above.

## Enable monitoring (optional, user-run)

```bash
numbat hook install --agent all --emit all   # observe-only hooks + live event stream
numbat hook status                            # verify coverage
```

The plugin works read-only whether or not hooks are installed; hooks make
it live.
