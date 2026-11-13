# Netline

A network lineage tracker for Omarchy: which process pulled what from where,
with outliers flagged and two map views one click away.

Passive capture only. The kernel already accounts every connection, so Netline
reads `conntrack` rather than sniffing packets for attribution; it does not
proxy, block, or modify traffic.

## What it shows

- **Bar widget** — a glyph whose colour states the answer: dim when nothing is
  flagged, accent when traffic is flowing, urgent when something is an outlier.
  The number next to it is the flag count.
- **Hex map** (`/`) — one hex cell per destination, tinted by share of traffic.
  The lightest view: ~7 KB, CSS `clip-path` only, no canvas.
- **Arc map** (`/arc`) — process → destination arcs, arc weight = bytes, dot
  direction = who pulled. Denser, for when you want the per-link detail.

## Requirements

- `net.netfilter.nf_conntrack_acct=1` — **required**. Without it conntrack
  reports no `bytes=` fields, every byte delta is zero, and the daemon silently
  drops every row while the service stays green. Install the sysctl:

```bash
echo 'net.netfilter.nf_conntrack_acct = 1' \
  | sudo tee /etc/sysctl.d/90-netline-conntrack-acct.conf
sudo sysctl -w net.netfilter.nf_conntrack_acct=1
```

- Root for the collector (`/proc/net/nf_conntrack` is root-only).
- Python 3.11+ with `sqlite3`. No third-party packages.

## Install

```bash
omarchy plugin add https://github.com/duketopceo/omarchy-netline
```

Then install the collector service and the GUI unit from `systemd/`, and edit
the `NETLINE_HOME` line if your operator account is not `lukekimball`.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | Plugin contract: `kinds: ["bar-widget"]`, category System |
| `Panel.qml` | Bar glyph and dropdown |
| `bin/netline.py` | Collector: conntrack poll, SQLite store, classifier |
| `bin/netline-gui.py` | Read-only HTTP server for the maps and `/api/data` |
| `bin/gui-hex.html` | Hex map (default view) |
| `bin/gui.html` | Arc map |
| `bin/status.py` | One-shot status JSON the bar polls |
| `bin/netline-restart.sh` | Bounce the user GUI unit then the system collector |
| `systemd/` | Collector and GUI units |

## Data

Everything stays local in `~/.local/share/netline/netline.db` (SQLite, WAL).
The GUI opens it `mode=ro`; only the collector writes. Hourly buckets, pruned
weekly by `netline-prune.timer`. Only rolled-up numbers leave the process — no
packet contents, and no URL paths beyond hostnames conntrack already named.

## License

MIT. See [LICENSE](LICENSE).
