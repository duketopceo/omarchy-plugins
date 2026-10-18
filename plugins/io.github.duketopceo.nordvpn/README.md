# NordVPN — Omarchy bar widget

Binary on/off VPN control in the Omarchy bar: the glyph is the switch.

- **OFF** → click opens a location picker (countries → cities → recommended
  servers from NordVPN's public API); picking connects.
- **ON** → click disconnects, all the way off.
- Extras: connected detail (hostname/IP/uptime/protocol) and a kill-switch
  toggle. That's it — no semi-states, no settings sprawl.

## Requirements

- `nordvpn-bin` package (CLI + daemon). There is no ARM64 GUI — this widget
  is the interface.
- `nordvpnd.service` enabled and running (`sudo systemctl enable --now nordvpnd`).
- User in the `nordvpn` group (`sudo usermod -aG nordvpn $USER`, re-login).
- Logged in (`nordvpn login`).

## Install

This plugin lives in the `omarchy-plugins` umbrella repo; each plugin dir
subtree-publishes to its own repo for `omarchy plugin add`:

```bash
omarchy plugin add io.github.duketopceo.nordvpn
# or from the umbrella checkout:
~/Documents/github/personal/omarchy-plugins/scripts/install.sh --copy io.github.duketopceo.nordvpn
```

Then add the widget via Omarchy bar settings (Plugins → NordVPN). Default
section: center.

## Remove

```bash
omarchy plugin remove io.github.duketopceo.nordvpn
```

## How it works

`bin/probe_nordvpn.py` emits one JSON object per verb:

| Verb | Data source |
|---|---|
| `status` | `nordvpn status` + `nordvpn settings` (every ~20s) |
| `countries` | `api.nordvpn.com/v1/servers/countries` → `nordvpn countries` fallback |
| `servers <country_id>` | `api.nordvpn.com/v1/servers/recommendations` |
| `connect [target]` | `nordvpn connect` (server short-name, country, country+city) |
| `disconnect` / `killswitch on\|off` | `nordvpn` CLI |

The picker works offline — without API access it falls back to the CLI's
flat country list.
