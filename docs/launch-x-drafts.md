# X launch drafts — perplexity-tool plugins

Post order suggestion: combined thread (announcement) or three standalone posts
a day apart. Marketplace listing links go live when `approved-and-verified` —
the repo links work today.

## Option A — combined launch thread

**Post 1/4:**

```
New on the Omarchy bar: three plugins that wrap Perplexity's open-source tools.

🐝 bumblebee — supply-chain exposure radar
🦡 numbat — AI-agent activity monitor
🔍 pplx — quick-ask search, no browser needed

All read-only, all BYO-binary. Marketplace submissions in.
```

**Post 2/4 (bumblebee):**

```
bumblebee scans your installed packages + lockfiles against a
known-compromise catalog on a 6h cache. Shield goes red on the bar when
something you have installed shows up in an advisory.

Ships a curated starter catalog; drop your own advisories in catalog.d/.

github.com/duketopceo/omarchy-bumblebee
```

**Post 3/4 (numbat):**

```
numbat answers "what are my coding agents actually doing?" — findings feed +
per-agent activity, straight from Perplexity's endpoint monitor.

Strictly read-only: never installs hooks, never touches enforce mode.

github.com/duketopceo/omarchy-numbat
```

**Post 4/4 (pplx):**

```
pplx puts Perplexity Search in a bar dropdown — type, enter, grounded
results with sources. BYOK; your key travels via env/keyring only, never
the command line.

github.com/duketopceo/omarchy-pplx

#omarchy #hyprland
```

## Option B — three standalone posts

**bumblebee:**

```
An advisory names a package. Do you have it installed? bumblebee answers
on your Omarchy bar — periodic supply-chain scans vs a known-compromise
catalog, red shield when it hits.

github.com/duketopceo/omarchy-bumblebee
```

**numbat:**

```
Running coding agents on your laptop? numbat puts a radar on the Omarchy
bar — which agents are active, what findings fired in the last 24h.
Read-only by contract.

github.com/duketopceo/omarchy-numbat
```

**pplx:**

```
Perplexity search without leaving the desktop. Quick-ask field in the bar,
grounded answers with sources, BYOK via env or keyring.

github.com/duketopceo/omarchy-pplx
```
