# Neo: landscape (2026-10-11)

Scope note: a short pass for a small plugin. One to three web searches, results read from search summaries only, not full pages. Items marked "not re-fetched" were not opened. Treat as a starting point, not a survey.

## Who else does this

| Project | What it does (as found) |
|---|---|
| [BrowserOS](https://www.browseros.com) | The browser whose neo sidecar this widget supervises. Cockpit and audit UI live in the browser, not the bar. |
| [systemd user units](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html) | What the widget wraps (`systemctl --user show/start/stop`). |
| [Model Context Protocol](https://modelcontextprotocol.io) | The `initialize` call the widget uses as its truth test. |

## What they do better and worse

No comparable bar widget was found in this pass; generic systemd tray monitors show unit state but not whether the MCP path answers.

## What users expect

Know in one glance whether agents can reach the browser, and restart it without a terminal.

## What is unique here

MCP `initialize` answering `serverInfo` is the health signal, not a bound socket; it is deliberately machine-shaped to one sidecar layout.

## Code facts used

Read directly from this repo: `Panel.qml` colour use (`Color.*`, `Style.*`), timers, animations and tab structure; `manifest.json`; `AGENTS.md`. See `DESIGN.md` for the audit.
