# Bumblebee: landscape (2026-10-11)

Scope note: a short pass for a small plugin. One to three web searches, results read from search summaries only, not full pages. Items marked "not re-fetched" were not opened. Treat as a starting point, not a survey.

## Who else does this

| Project | What it does (as found) |
|---|---|
| [OSV-Scanner / OSV.dev](https://github.com/google/osv-scanner) | Google; lockfile scans against the open OSV database. Broad ecosystem coverage; vulnerability-oriented, not a bar widget. |
| [GuardDog (Datadog)](https://dev.to/githubopensource/stop-supply-chain-attacks-guarddog-scans-your-dependencies-for-hidden-malware-2g8p) | Python CLI, Semgrep rules plus metadata heuristics over npm, PyPI, Go, GitHub Actions, VS Code extensions. Heuristic detection of unknown malware; no ambient desktop surface. |
| [supplyscan](https://pkg.go.dev/github.com/undont/supplyscan) | Go CLI combining Datadog IOCs, GitHub advisories and OSV.dev for JS and Python lockfiles. |
| [supply-chain-guard (Socket listing)](https://socket.dev/npm/package/supply-chain-guard) | Offline scan, non-zero exit codes for CI gating. |
| [perplexityai/bumblebee (upstream)](https://github.com/perplexityai/bumblebee) | The scanner this plugin wraps; ships no catalog of its own beyond `threat_intel/` in release tarballs. |

## What they do better and worse

Competitors cover more ecosystems and detect unknown malware heuristically. They are CI or CLI tools: you run them, you read the output.

## What users expect

Zero false-alarm fatigue, a freshness indicator on the catalog, and no network use beyond a pinned refresh.

## What is unique here

An always-on, local, read-only radar on the desktop bar: it scans MCP configs and editor extension manifests as well as lockfiles, caches the result, and toasts only on new exposures (delta), with per-exposure muting.

## Code facts used

Read directly from this repo: `Panel.qml` colour use (`Color.*`, `Style.*`), timers, animations and tab structure; `manifest.json`; `AGENTS.md`. See `DESIGN.md` for the audit.
