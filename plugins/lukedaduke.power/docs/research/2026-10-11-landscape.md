# Landscape: omarchy-power (battery and power-profile bar widget)

Date: 2026-10-11. Sources are each project's own repository or site, fetched with `gh` and `curl`
(HTTP 200 checked). Star counts are from the GitHub API on this date. The "unverified" tag below means: described by the project itself (repo description or README), not independently tested here.

## Who else does this

| Project | What it is (per the project) | Better than this plugin | Worse than this plugin |
|---|---|---|---|
| [Waybar](https://github.com/Alexays/Waybar) battery module | Highly customizable Wayland bar, 12k stars, MIT | Mature, huge user base, many themes | Not an Omarchy plugin; no charge history graph or consumers list in the module |
| [TLP](https://github.com/linrunner/TLP) | Optimize Linux laptop battery life, 3.3k stars, GPL-2.0 | Actually tunes the system (charge thresholds, device power) | CLI/service only, no live UI; on Asahi this machine uses power-profiles-daemon instead of TLP |
| [auto-cpufreq](https://github.com/AdnanHodzic/auto-cpufreq) | Automatic CPU speed and power optimizer, 7.8k stars, GPL-3.0 | Automatic governor switching | Not a bar widget; overlaps profile switching |
| [power-profiles-daemon](https://gitlab.freedesktop.org/upower/power-profiles-daemon) | The D-Bus profile service this plugin drives through `omarchy-powerprofiles-*` | Canonical backend | No UI of its own |
| [Noctalia shell](https://github.com/noctalia-dev/noctalia) and [Caelestia shell](https://github.com/caelestia-dots/shell) | Customizable Wayland desktop shells, 11k and 13k stars | Built-in battery widgets inside a full shell | Not drop-in for Omarchy; a different ecosystem |

## What users expect

- Battery percent and state at a glance in the bar; one click to the details.
- Profile switch (performance, balanced, power-saver) without a terminal.
- Honest "time remaining" and a health indicator. Users of Apple Silicon laptops also expect the charge limit to be explained.

## What is unique here

- A battery widget that sits inside Omarchy's own plugin contract and follows its theme (`qs.Commons`).
- Charge history as a terminal-style graph, sampled by `battery_helper.py` into `~/.local/state/omarchy/battery_history.json`, plus a per-process "who is draining the pack" list with estimated watts.
- Knows about the 80 percent charge-limit state on Apple Silicon (`chargeThresholdActive`), so "not charging" at 80 percent is shown as intended rather than as a fault.
