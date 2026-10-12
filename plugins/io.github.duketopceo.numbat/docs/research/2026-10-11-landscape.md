# Landscape: omarchy-numbat (AI-agent activity radar)

Date: 2026-10-11. Sources are each project's own repository or site, fetched with `gh` and `curl`
(HTTP 200 checked). Star counts are from the GitHub API on this date. The "unverified" tag below means: described by the project itself (repo description or README), not independently tested here.

## Who else does this

| Project | What it is (per the project) | Better than this plugin | Worse than this plugin |
|---|---|---|---|
| [perplexityai/numbat](https://github.com/perplexityai/numbat) | Visibility into AI agent activity on endpoints, with on-device detection, optional pre-action blocking, forensic reconstruction; 1.1k stars, Apache-2.0 | The source of truth, supports enforcement | CLI and files only; no ambient desktop view (this plugin is that view) |
| [Waybar](https://github.com/Alexays/Waybar) custom modules | Generic bar module scripting | Could wrap `numbat` output | No findings feed, toasts or watermark logic |
| [Noctalia](https://github.com/noctalia-dev/noctalia) and [Caelestia](https://github.com/caelestia-dots/shell) | Desktop shells | Ecosystems with notification centres | No numbat integration found by name |

## What users expect

- Ambient: know something happened without opening a terminal, and not be spammed.
- Trust: a monitor must be read-only and say so.
- A clear first-run path when the binary or hooks are missing (the AUR `numbat` package is an unrelated language; the README warns about it).

## What is unique here

- The only Omarchy-native view of numbat: a read-only consumer. It never installs hooks, never writes `~/.numbat`, never enables enforce mode (README privacy section).
- Toast discipline (watermark so first launch does not storm, per `rule|agent` cooldown, severity gating, do-not-disturb) is more careful than a plain bar script.
- Optional Jev agent review via OpenRouter, opt-in and key held by the Python helper only.
