# Home Index

Omarchy menu helper for `~/INDEX.md` + auto-detected lanes.

Lanes are discovered from the layout (first child of `~/Work/`, first child of
`~/Projects/`, plus `~/Agents/`, `~/Pictures/Screenshots/`, and
`~/.config/omarchy/` when present). No usernames, orgs, or host paths are
hardcoded — the plugin works on any Omarchy setup.

## Use

```bash
bin/homeindex open            # open ~/INDEX.md
bin/homeindex open work       # open first ~/Work/ lane (also: projects|agents|shots)
bin/homeindex audit           # run home-index-audit, notify last line
bin/homeindex rebuild         # auto-detect home-index indexer under ~/Projects/*/home-index/
```

Wire into the Omarchy menu via `omarchy-menu.jsonc` entries that call `bin/homeindex`.
