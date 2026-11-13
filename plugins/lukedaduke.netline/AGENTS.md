# Netline

Network lineage on the Omarchy bar. Passive `conntrack` capture into SQLite,
with a hex map and an arc map served read-only from the same store.

## The rule that bites

`net.netfilter.nf_conntrack_acct` **must** be 1. The collector derives per-flow
bytes from conntrack counters, so with accounting off every row has a zero
delta and is skipped. The service stays `active`, the widget shows nothing, and
there is no error anywhere — this is the failure mode that cost a debugging
session. Check it first:

```bash
cat /proc/sys/net/netfilter/nf_conntrack_acct     # must print 1
grep -c bytes= /proc/net/nf_conntrack            # must be > 0 under traffic
```

## Layout exception

The collector, GUI server, and both HTML maps live in `bin/` beside
`status.py`, not at the plugin root. `Panel.qml` resolves `status.py` through
`pluginRoot`, so moving files between `bin/` and the root changes the exec path
and silently breaks the bar.

## Two views, one payload

`netline-gui.py` serves `/` (hex, ~7 KB, clip-path only) and `/arc` (canvas).
Both read `/api/data`, whose shape is `stats`, `dests`, `procs`, `links`,
`flags`. Destination objects carry `name`, `ip`, `out`, `in`, `bytes`, `flows`,
`flag`. The hex map depends on `stats`; changing that key blanks its header.

## Privilege split

The collector is a **system** unit running as root (`/proc/net/nf_conntrack` is
root-only). The GUI is a **user** unit binding `127.0.0.1:8899` and opening the
store `mode=ro`. The plugin never writes to the database.

## Testing a change

```bash
python3 -c "import ast; [ast.parse(open(f).read()) for f in
  ('bin/netline.py','bin/netline-gui.py','bin/status.py')]"
curl -sS http://127.0.0.1:8899/api/data | python3 -m json.tool | head
```

For the maps, load them with a served payload rather than a static file: both
fetch `/api/data` on load and render nothing without it.
