# X launch — posted 2026-09-17 (v0.2.0)

Final copy as posted. Thread of 4 posts, all under 280 chars, Perplexity
credited for the upstream tools.

# X launch — Dayflow posted 2026-10-03 (v1.5.0)

Single-post format (video screencast attached at post time). First of the
flagship series: dayflow → wisp → omaseal, spaced across days.

## Posted

```
Ported Dayflow to Linux — a private work journal that writes itself.

A vision model summarizes your screen every 15 min into a searchable timeline: standup drafts, agent-session recaps, forecasts.

Local-first, ~25MB RAM, any vision model or fully local via Ollama.

github.com/duketopceo/dayflow-linux
```

## Follow-up

- Wisp post next (draft below). Marketplace: submitted as #10092 via new
  `duketopceo/omarchy-wisp` repo (subtree split of wisp's `shell-plugin/`);
  validation passed, baseline `remote-git-execution-unpinned` fixed by
  pinning the wispd install to v0.9.0 commit — awaiting maintainer
  `approved-and-verified`.
- OmaSeal #5620 blocker fixed in duketopceo/OmaSeal#39 (`c84b1569`,
  VerifyStatus sender filter) — awaiting maintainer rescan.
- Marketplace verify issues verified current (all four pin published
  HEADs): #7595 numbat `03aa659`, #7594 bumblebee `82db872`,
  #7596 pplx `92dff60`, #7587 agents `8d56cd2` — awaiting maintainer.

## Wisp draft (pending)

```
Built a resident voice companion for Omarchy: Super+D, speak, done.

Wisp hears you, reads your screen for context, then answers at your cursor, drives the desktop step by step, or spawns a coding agent in the background.

whisper.cpp + a small router model — no cloud roundtrip for the ear.

github.com/duketopceo/wisp
```

## OmaSeal draft (pending #5620 fix)

```
Omarchy plugins keep stashing API keys in .env files and dotfiles. So I built OmaSeal — one keyring for the desktop, plugins, and every agent.

gnome-keyring underneath, MCP for Claude/Codex/Cursor, 1Password/Bitwarden fallback. Store once, use everywhere.

github.com/duketopceo/OmaSeal
```



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
