# Connections: landscape (2026-10-11)

Scope note: a short pass for a small plugin. One to three web searches, results read from search summaries only, not full pages. Items marked "not re-fetched" were not opened. Treat as a starting point, not a survey.

## Who else does this

| Project | What it does (as found) |
|---|---|
| [nm-applet](https://mankier.com/package/network-manager-applet) | GTK tray applet for NetworkManager; needs a system tray. |
| [Blueman](https://dyn.manpages.debian.org/wheezy/blueman/blueman-applet.1.en.html) | Bluetooth tray applet; full device management in a context menu. |
| [networkmanager-dmenu](https://github.com/firecat53/networkmanager-dmenu) | Launcher-menu replacement for nm-applet; can toggle Wi-Fi, WWAN, Bluetooth; Bluetooth optional. |
| [Omarchy stock bluetooth and network widgets](https://github.com/basecamp/omarchy) | Two separate bar icons; this plugin embeds their panels. |

## What they do better and worse

Tray applets are heavier and need a tray; the dmenu route has no at-a-glance state. Stock Omarchy gives two separate icons with full panels.

## What users expect

Click opens a panel, a second action toggles the radio, state is visible without opening anything.

## What is unique here

One widget, two radios, with both stock dropdowns anchored under their own icons and no helper process.

## Code facts used

Read directly from this repo: `Panel.qml` colour use (`Color.*`, `Style.*`), timers, animations and tab structure; `manifest.json`; `AGENTS.md`. See `DESIGN.md` for the audit.
