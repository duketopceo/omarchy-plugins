# Landscape: omarchy-plugins (catalog and shared rules for the plugin family)

Date: 2026-10-11. Sources are each project's own repository or site, fetched with `gh` and `curl`
(HTTP 200 checked). Star counts are from the GitHub API on this date. The "unverified" tag below means: described by the project itself (repo description or README), not independently tested here.

## Who else does this

| Project | What it is (per the project) | Better than this plugin | Worse than this plugin |
|---|---|---|---|
| [Omarchy](https://github.com/omacom/omarchy) | The host: "Beautiful, Modern & Opinionated Linux", 44.6k stars | Defines the plugin contract and theme roles | Does not document colour contrast guarantees for plugins |
| plugins.omarchy.org | The marketplace; submission via its publish page (per this repo README) | Discovery | Per-repo, so shared rules must live in the catalog |
| [Noctalia](https://github.com/noctalia-dev/noctalia) and [Caelestia](https://github.com/caelestia-dev/shell) | Full shells with built-in widgets | Single coherent look | Not drop-in; a different plugin model |
| [Waybar](https://github.com/Alexays/Waybar) | Bar with modules, 12k stars | Large module ecosystem | Per-module styling by user CSS rather than a theme contract |

## What users expect

- A plugin that looks like it came with Omarchy and survives `omarchy theme set`.
- Safe by default: bounded input, fixed executables, no secret logging (the contract).
- Install by one command per plugin repo.

## What is unique here

- One catalog that is also a checked contract: manifest validation, plugin-contract checker, scorecard, host-integration checks, shared QML (`shared/qml`) synced into plugins with `sync-shared.py`.
- This family direction (Pilot Light): a measured contrast audit across all 22 bundled Omarchy themes, which the host does not publish.
