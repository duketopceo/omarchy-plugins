# X launch drafts — perplexity-tool plugins

Post order suggestion: combined thread (announcement) or three standalone posts
a day apart. Marketplace listing links go live when `approved-and-verified` —
the repo links work today. Updated for v0.2.0 (always-on services + toasts).

## Option A — combined launch thread

**Post 1/4:**

```
New on the Omarchy bar: three plugins that wrap Perplexity's open-source tools.

🐝 bumblebee — supply-chain exposure radar, now always-on
🦡 numbat — AI-agent activity monitor, now a live radar
🔍 Perplexity Search — quick-ask search, no browser needed

All read-only, all BYO-binary, x86 + ARM. Marketplace submissions in.
```

**Post 2/4 (bumblebee):**

```
bumblebee watches your installed packages + lockfiles against a
known-compromise catalog — a tiny in-shell service keeps scans fresh and
raises a toast only when a NEW exposure lands. Silent when clean.

Opt-in advisory refresh pulls Perplexity's own threat_intel feed.

github.com/duketopceo/omarchy-bumblebee
```

**Post 3/4 (numbat):**

```
numbat answers "what are my coding agents actually doing?" — findings feed,
per-agent activity, 24 wired integrations — and now a persistent watcher
that pops a severity-tinted toast the moment a new finding lands.

Strictly read-only: never installs hooks, never touches enforce mode.

github.com/duketopceo/omarchy-numbat
```

**Post 4/4 (pplx):**

```
Perplexity Search lives in a bar dropdown — type, enter, grounded results
with sources. Recency + context chips, one-click copy, query history.

BYOK; your key travels via env/keyring only, never the command line.

github.com/duketopceo/omarchy-pplx

#omarchy #hyprland
```

## Option B — three standalone posts

**bumblebee:**

```
An advisory names a package. Do you have it installed? bumblebee answers
on your Omarchy bar — background scan service, and a toast the moment a
NEW exposure matches. Zero noise when you're clean.

github.com/duketopceo/omarchy-bumblebee
```

**numbat:**

```
Running coding agents on your laptop? numbat puts a live radar on the
Omarchy bar — which agents are active, what findings fired — and a toast
within seconds of anything new. Read-only by contract.

github.com/duketopceo/omarchy-numbat
```

**pplx:**

```
Perplexity Search without leaving the desktop. Quick-ask field in the
bar, recency/context chips, grounded answers with sources, BYOK via env
or keyring.

github.com/duketopceo/omarchy-pplx
```

## Posting checklist

- [ ] Marketplace issues #7322/#7323/#7324 carry `approved-and-verified`
- [ ] Screenshots: bar glyphs + one toast + pplx Ask tab with chips
- [ ] Repo links live: omarchy-{bumblebee,numbat,pplx}
- [ ] Tag @omarchy + #hyprland on the thread
