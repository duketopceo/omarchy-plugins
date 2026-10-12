# Hardware Nexus: landscape (2026-10-11)

Scope note: a short pass for a small plugin. One to three web searches, results read from search summaries only, not full pages. Items marked "not re-fetched" were not opened. Treat as a starting point, not a survey.

## Who else does this

| Project | What it does (as found) |
|---|---|
| [hwloc / lstopo](https://hwloc.readthedocs.io/en/v2.x/doxygen/html/tools.html) | Hierarchical topology map (NUMA, sockets, cores); graphical, ASCII and XML export. CPU-centric; no USB or Bluetooth. |
| [lsusb -t](https://man7.org/linux/man-pages/man8/lsusb.8.html) | USB tree in the terminal; exact, no live updates. |
| [usbview](https://github.com/gregkh/usbview) | GTK USB tree viewer (not re-fetched in this pass). |
| [Blueman](https://dyn.manpages.debian.org/wheezy/blueman/blueman-applet.1.en.html) | Bluetooth device manager; not a cross-bus view. |

## What they do better and worse

hwloc is deeper on CPU and memory; lsusb is exact. Neither joins USB, Bluetooth, network and storage in one glanceable panel.

## What users expect

Plug something in and see it; unplug and see it go. Nothing writes to the system.

## What is unique here

One read-only panel across four buses with friendly USB names from a known-hardware dictionary, tolerant of missing tools by design.

## Code facts used

Read directly from this repo: `Panel.qml` colour use (`Color.*`, `Style.*`), timers, animations and tab structure; `manifest.json`; `AGENTS.md`. See `DESIGN.md` for the audit.
