# X launch — posted 2026-09-17 (v0.2.0)

Final copy as posted. Thread of 4 posts, all under 280 chars, Perplexity
credited for the upstream tools.

## Posted thread

**Post 1/4:**

```
New on the Omarchy bar: three plugins built on Perplexity's open-source agentic tools — credit to @perplexity_ai for open-sourcing numbat, bumblebee, and the pplx CLI.

All read-only, BYO-binary, x86 + ARM. Marketplace submissions in.
```

**Post 2/4:**

```
bumblebee scans installed packages + lockfiles against a known-compromise catalog. My plugin keeps scans fresh via a tiny in-shell service and pops a toast only on NEW exposures — silent when clean.

github.com/duketopceo/omarchy-bumblebee
```

**Post 3/4:**

```
numbat is Perplexity's agentic activity monitor — observe-only hooks across 24 coding agents. My plugin puts findings on the Omarchy bar and pops a severity-tinted toast when a new one lands.

github.com/duketopceo/omarchy-numbat
```

**Post 4/4:**

```
Perplexity Search in an Omarchy bar dropdown, powered by their pplx CLI + Search API. Type, enter, grounded results with sources. Recency/context chips, one-click copy, BYOK via env or keyring.

github.com/duketopceo/omarchy-pplx

#omarchy #hyprland
```

## Follow-up

- Marketplace issues #7322/#7323/#7324 await `approved-and-verified` —
  when listings go live, a short follow-up post with install links is the
  natural second beat.
- Repo links: github.com/duketopceo/omarchy-{bumblebee,numbat,pplx}
