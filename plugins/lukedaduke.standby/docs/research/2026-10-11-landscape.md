# Landscape: omarchy-standby (OLED nightstand overlay)

Date: 2026-10-11. Sources are each project's own repository or site, fetched with `gh` and `curl`
(HTTP 200 checked). Star counts are from the GitHub API on this date. The "unverified" tag below means: described by the project itself (repo description or README), not independently tested here.

## Who else does this

| Project | What it is (per the project) | Better than this plugin | Worse than this plugin |
|---|---|---|---|
| iPhone StandBy | Horizontal nightstand clock mode on iPhone (the README names it as the model) | Polished, widgets, night red mode | Phone only |
| [Open-Meteo](https://open-meteo.com) | Free weather API the plugin calls | Free, no key | A data source, not a display |
| [Quickshell](https://quickshell.org) overlays in desktop shells such as [Noctalia](https://github.com/noctalia-dev/noctalia) | Customizable Wayland shells | Rich widget systems | Not an OLED-first, black-background overlay |
| Screensavers and idle daemons (`omarchy.idle`, `omarchy.lock`) | Host behaviour | Integrated | Standby deliberately does not replace them |

## What users expect

- It appears instantly and goes away with one key.
- It is dim enough to sleep next to. The clock must be readable at arm's length at night.
- No surprise network calls or lock behaviour.

## What is unique here

- A summon-on-demand overlay (`omarchy-shell shell summon lukedaduke.standby`) that does not touch the screensaver or lock screen.
- OLED-first: true black, dim content, red tint, brightness toggle, caffeine mode that writes the host's stay-awake indicator.
- Weather location comes from a settings file if present, with an IP-geolocation fallback in `bin/standby-data` (privacy note: that fallback makes one network lookup).
