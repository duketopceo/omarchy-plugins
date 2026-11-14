# Home Index

Omarchy menu helper for `~/INDEX.md` + home lanes:

| Lane | Path |
|---|---|
| Work (Bartlett) | `~/Work/bartlett` |
| Personal (duketopceo) | `~/Projects/duketopceo` |
| Agents | `~/Agents` |
| Screenshots | `~/Pictures/Screenshots` |

## Use

```bash
bin/homeindex open            # open ~/INDEX.md
bin/homeindex open work       # open ~/Work/bartlett (duke|agents|shots too)
bin/homeindex audit           # run home-index-audit, notify last line
bin/homeindex rebuild         # run ~/Projects/duketopceo/home-index/index.py
```

Wire into the Omarchy menu via `omarchy-menu.jsonc` entries that call `bin/homeindex`.
