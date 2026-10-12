# Landscape: omarchy-fan (resource monitor and fan control bar widget)

Date: 2026-10-11. Sources are each project's own repository or site, fetched with `gh` and `curl`
(HTTP 200 checked). Star counts are from the GitHub API on this date. The "unverified" tag below means: described by the project itself (repo description or README), not independently tested here.

## Who else does this

| Project | What it is (per the project) | Better than this plugin | Worse than this plugin |
|---|---|---|---|
| [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl) | Systemd service to control Framework laptop fans, 464 stars | Focused, scriptable curves | No panel, no process list |
| [macfanctld](https://github.com/MikaelStrom/macfanctld) | Fan control for MacBook (Intel era), 78 stars | Long track record on Macs | Not for Apple Silicon (`macsmc_hwmon`) as far as its description states |
| [CoreCtrl](https://gitlab.com/corectrl/corectrl) | GPU/CPU control GUI | Rich GPU control | Standalone window, not a bar widget |
| [Mission Center](https://gitlab.com/mission-center-devs/mission-center) | Resource monitor app (the polish plan cites it as the target look) | Polished cards and graphs | Standalone app; no fan control; not in the bar |
| [Waybar](https://github.com/Alexays/Waybar) temperature and cpu modules | Bar modules, MIT | Ubiquitous | One number per module; no fan control, no kill |

## What users expect

- Temperatures and fan RPM visible without opening a terminal; a safe auto mode with named presets.
- Honest degradation: telemetry-only when the helper is absent (the panel says so).
- A kill action that names exactly what dies.

## What is unique here

- Telemetry, process kill and fan control in one Omarchy bar widget that follows the theme.
- Fan control on Apple Silicon: `omarchy-fan-daemon` drives `fan*_target` on `macsmc_hwmon` and `pwm*` on `dell_smm`, through a root helper package so the plugin itself never elevates.
- Process list with friendly aliases (e.g. disambiguating Ollama's backend from other `llama-server`s) so the kill target is unambiguous.
