# Neo — `io.github.duketopceo.neo`

Bar status + control widget for the local **BrowserOS neo** sidecar: stock
headless chromium + the `browserclaw` CDP shim + `browseros-claw-server`,
run as systemd **user** units and driven by agents over MCP at
`http://127.0.0.1:9211/mcp`.

## What it shows

- Per-unit state for `browserclaw-chromium`, `browserclaw-shim`,
  `browserclaw-server` (active/sub-state/pid) plus whether each port —
  `49337` (CDP), `49338` (shim), `9211` (MCP) — is actually bound
- MCP health: a real `initialize` POST answers `serverInfo`, so "RUNNING"
  means the agent path works, not just that sockets are open
- The MCP endpoint with a copy button (`wl-copy`)
- Start / Restart / Stop controls (bounded `systemctl --user` calls, one
  helper invocation, hard deadlines on both sides)

The bar glyph tints urgent while any unit is down or MCP doesn't answer.

## Machine coupling

This plugin is deliberately machine-shaped: unit names, ports, and the MCP
endpoint are Luke's sidecar layout (`~/.local/share/browserclaw/` +
`~/.config/systemd/user/browserclaw-*.service`). On a machine without that
sidecar it renders DOWN — install it only where the sidecar exists.

## Privacy & security posture

- No telemetry, no third-party network calls. The only traffic is loopback:
  an MCP `initialize` to `127.0.0.1:9211` (3s) and a `/json/list` GET to the
  CDP shim on `127.0.0.1:49338` (2s), both read-only.
- The helper execs `/usr/bin/systemctl` and `/usr/bin/wl-copy` by absolute
  path under a fixed `PATH`, with bounded output and a hard job deadline.
- `status` is pure stat: one `systemctl --user show`, one `/proc/net/tcp`
  read, one bounded MCP POST, one `/json/list` GET on the CDP shim for the
  open-tab count. Control verbs (`start|stop|restart [unit]`) only run on
  click — each unit row carries its own restart, the control row drives
  the whole stack.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-neo
omarchy plugin enable io.github.duketopceo.neo
```

MIT — see [LICENSE](LICENSE).
