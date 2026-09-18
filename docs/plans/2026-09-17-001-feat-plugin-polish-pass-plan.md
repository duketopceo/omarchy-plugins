---
title: "feat: Final polish + always-on services for the three Perplexity plugins"
date: 2026-09-17
type: feat
depth: deep
origin: docs/plans/2026-09-16-001-feat-perplexity-tool-plugins-plan.md
---

# feat: Final polish — live services, popups, brand, public release readiness

## Summary

Dogfooding surfaced the real remaining work to take bumblebee, numbat, and
pplx from "live on one bar" to "shippable public plugins": numbat becomes a
true always-on radar (live event stream + findings watcher service +
severity popup), bumblebee becomes a true background scanner (staleness
service + exposure popup + opt-in advisory refresh), pplx gets its search
options row and a Perplexity-brand makeover, and the trio ships with proper
upstream attribution, cross-arch support (x86_64 + aarch64), expanded
tests, and one batched marketplace re-attestation.

## Problem Frame

Verified gaps against installed upstream binaries and real usage:

1. **numbat is a scanner, not yet a radar.** Events come from a 10-min
   `numbat scan` cache; `numbat hook install --emit all` exists and writes
   live events+findings to `~/.numbat/records.ndjson`. The plugin neither
   tails that file nor runs any persistent watcher, so findings surface
   only when the user opens the panel.
2. **No plugin surfaces findings when the bar is closed.** Omarchy
   manifests support `service` (in-shell persistent component, ~0 load)
   and `overlay` (popup surface) kinds — notification-center and
   lock-explorer ship exactly that shape. Our plugins only declare
   `bar-widget`.
3. **pplx exposes only the bare query.** Upstream flags
   (`--recency-filter`, `--search-context-size`, `-n`, `--domains`,
   `--intent`) are unused; results can't be copied; the panel carries no
   Perplexity brand identity.
4. **bumblebee's catalog is frozen at ship time.** Upstream ships a
   `threat_intel/` dir per release; no refresh path exists.
5. **Public-release readiness is incomplete.** No upstream attribution
   files, no ARM+x86 CI signal, no consolidated final security pass —
   all required before other Omarchy users install these.

## Requirements

- R1. Numbat shows live hook events within one poll when hooks emit them;
  a `service` component watches the record files at ~0 load and a new
  finding raises a popup — even with the dropdown closed.
- R2. Bumblebee's scan stays fresh without user interaction (staleness
  service on the existing 6h cadence); a new exposure raises an urgent
  popup; advisory refresh is opt-in and integrity-pinned.
- R3. Pplx Ask exposes recency/context selection reaching the CLI as
  allowlisted flags; results copy URLs; history entries can be deleted.
- R4. Pplx carries a Perplexity-brand identity pass — glyph, wordmark,
  copy, preview card — expressed only through theme-derived colors
  (repo rule: no hardcoded hex).
- R5. Each plugin documents its upstream dependency honestly: name, repo,
  license (Apache-2.0), install methods for **x86_64 and aarch64**, and
  the plugin→tool boundary (wrapper, not vendored).
- R6. CI runs the suite on both architectures; every helper keeps the
  hardening contract (fixed-path exec, scrubbed env, bounded I/O,
  `O_NOFOLLOW`, atomic 0600 writes, PlainText sinks, group-kill
  deadlines, no shell, no secrets in argv/logs/output).
- R7. One republish wave — all units land, suite green, then one
  `publish.sh` per repo and one consolidated comment per marketplace
  issue (#7322–7324). No pushes between units and the wave.

## Key Technical Decisions

- **KTD1 — services are QML components in-shell, not daemons.** A
  `service` entry point is a Quickshell component the shell keeps loaded
  (`kinds:["service","bar-widget","overlay"]`, `entryPoints.service` /
  `entryPoints.overlay` — the shape notification-center and
  lock-explorer ship). Our services stat small files on a Timer —
  `findings.ndjson`/`records.ndjson` mtime+size for numbat (~1 stat/poll),
  `last-scan.json` age for bumblebee (~1 stat/hour). No processes left
  running, no timers under 10s, work happens only on change.
- **KTD2 — popups are `overlay` entry points, not notify-send.** A custom
  overlay keeps the dayflow visual language and severity tint; freedesktop
  notifications are the fallback consideration but pull the user into a
  different UI. Overlays fire only on *new* findings/exposures — the
  service tracks a last-seen watermark (count + newest timestamp) persisted
  in the existing state dirs.
- **KTD3 — `records.ndjson` is the live event source when present.**
  `--emit all` at hook install writes events there (docs/cli.md:639).
  Probe tails it with the existing bounded `O_NOFOLLOW` machinery; live
  events take precedence over scan-cached events, deduped on
  `(agent, observed_at, kind)`; `events_live` flag reports which feed is
  active. Emit-all remains the user's choice — the plugin never runs
  `hook install`; docs and the setup pane present it as the richer option.
- **KTD4 — flag allowlist, not passthrough.** Panel chip state maps to a
  fixed flag set: recency ∈ {hour,day,week,month,year}, context ∈
  {low,medium,high}, limit ∈ 1..20. Anything else produces no flag.
- **KTD5 — advisory refresh is offline-by-default and pinned.**
  `refresh_catalog.py` runs only when invoked (button or CLI): pinned
  `RELEASE_TAG` + `github.com/perplexityai/bumblebee` tarball over HTTPS,
  bounded download (~64MiB), extract `threat_intel/` only, validate each
  entry against the `0.1.0` schema, merge to `catalog.d/upstream.json`
  atomically at 0600. No upstream signature infra exists; the pin (repo +
  tag + HTTPS) is the documented integrity story.
- **KTD6 — brand lives in glyph/wordmark/copy, not color.** Perplexity
  identity = magnifier mark, "Perplexity Search" naming, honest
  "Powered by the Perplexity Search API" copy, preview-card restyle.
  Colors stay theme-derived (AGENTS.md hard rule); Perplexity's own UI
  accent is a near-match for typical Omarchy accents anyway.
- **KTD7 — attribution is a first-class file.** Each plugin ships an
  `UPSTREAM.md` (tool name, repo URL, Apache-2.0 license, install
  commands for x86_64 + aarch64, what the plugin does vs. what the tool
  does) plus a matching README section. No upstream code is vendored —
  attribution is credit+docs, not license compliance plumbing.
- **KTD8 — arch support is a CI matrix, not code.** Plugins are QML+python
  (arch-independent); the real arch question is upstream binaries, which
  ship linux/amd64 + linux/arm64 for all three tools. CI adds an
  `ubuntu-24.04-arm` leg alongside x86 `ubuntu-latest` so the suite —
  including the helper tests that don't need the binaries — proves both.

## High-Level Technical Design

```
each plugin (one manifest, up to three entry points)
│
├─ entryPoints.service  → Service.qml  (shell keeps loaded, ~0 load)
│    numbat:   Timer 5s → stat findings.ndjson + records.ndjson
│              mtime/size changed → exec probe tail → new finding? → raise overlay
│    bumblebee:Timer 1h → stat last-scan.json → stale? → exec scan --force
│              new exposure? → raise overlay
│
├─ entryPoints.overlay  → Overlay.qml  (popup on NEW findings only)
│    severity-tinted card: rule · agent · title · rel-time · "Open" → bar dropdown
│
└─ entryPoints.barWidget→ Panel.qml    (existing, unchanged role)
```

## Implementation Units

### U1. Numbat live event stream

**Goal:** events surface streams live when hooks emit them; scan cache
becomes backfill, not the primary feed.

**Requirements:** R1, R6
**Dependencies:** none
**Files:**
- `plugins/io.github.duketopceo.numbat/bin/probe_numbat.py` (modify)
- `tests/test_numbat.py` (modify)
- `plugins/io.github.duketopceo.numbat/Panel.qml` (modify — Log tab
  source hint)
- `plugins/io.github.duketopceo.numbat/README.md` (modify — emit-all
  install guidance)

**Approach:**
- Tail `~/.numbat/records.ndjson` every poll alongside `findings.ndjson`
  (bounded 256KiB, descriptor-relative, `O_NOFOLLOW` — reuse `_read_tail`).
- Live events merge with scan-cached events, deduped on
  `(agent, observed_at, kind)`; live sort first. Emit `events_live:
  true|false` and a `live_records_path` when the file exists.
- findings: keep `findings.ndjson` as primary live source; merge
  record-type `finding` entries from records.ndjson too (emit-all hooks
  may write both sinks — verify at implementation, merge both either way).
- Panel Log tab: `STREAMED`/`SCANNED` source hint in the section header.
- Setup pane + README: `numbat hook install --agent all --emit all` as
  the recommended install (still monitor-mode, never enforce).

**Test scenarios:**
- records.ndjson with live events + empty findings tail → events emitted,
  `events_live: true`
- records.ndjson absent → scan-cached events only, `events_live: false`
- identical event in live tail and scan cache → single entry, live wins
- live finding in records.ndjson → merged into findings list
- records.ndjson symlink → not followed, scan data still emitted
- tail >256KiB → bounded read keeps newest
- malformed lines → skipped, no crash

**Verification:** after `--emit all` reinstall here, a live agent action
appears in Log within one poll — no scan wait.

### U2. Numbat service + finding overlay

**Goal:** a persistent in-shell watcher raises a severity-tinted popup on
new findings — the radar works with the dropdown closed.

**Requirements:** R1, R6
**Dependencies:** U1 (probe emits the fields the service consumes)
**Files:**
- `plugins/io.github.duketopceo.numbat/Service.qml` (new)
- `plugins/io.github.duketopceo.numbat/Overlay.qml` (new)
- `plugins/io.github.duketopceo.numbat/manifest.json` (modify — kinds +
  entryPoints)
- `plugins/io.github.duketopceo.numbat/bin/probe_numbat.py` (modify —
  `tail` verb for the service's cheap poll)
- `tests/test_numbat.py` (modify — tail verb)
- `tests/test_manifests.py` (modify if entryPoint coverage needs it)

**Approach:**
- `Service.qml`: 5s Timer → stat the two record files (mtime+size via a
  tiny `probe_numbat.py tail` exec that returns only counts+newest-ts —
  keeps the shell free of file I/O and the helper owns all reads). On
  change → full tail → watermark-diff new findings → raise overlay.
  Watermark persists in the existing state dir (0600, atomic — helper-owned).
- `Overlay.qml`: dayflow-styled severity card — rule title, agent,
  rel-time, severity chip; "Open" action focuses the bar dropdown;
  auto-dismiss ~8s; queues if multiple findings land in one poll (max 3
  stacked).
- Manifest: `kinds: ["service","bar-widget","overlay"]`,
  `entryPoints: {service:"Service.qml", barWidget:"Panel.qml",
  overlay:"Overlay.qml"}` — verify validator passes the new kind keys.
- All new Text sinks PlainText; service exec uses the same
  fixed-path/scrubbed-env/deadline contract as the panel.

**Test scenarios:**
- tail verb returns `{findings_count, newest_finding_ts, events_count}`
  without scanning
- watermark file absent → first poll records baseline, no popup storm
- N findings arrive between polls → overlay queues ≤3, watermark advances
- findings file truncated/rotated → watermark resets, no crash
- manifest validates with all three kinds + entryPoints

**Verification:** inject a test finding line → popup appears ≤5s with
severity tint; no popup on repeat polls.

### U3. Pplx search options + copy + history delete

**Goal:** Ask exposes upstream's real modifiers; results copy; history
is manageable.

**Requirements:** R3, R6
**Dependencies:** none
**Files:**
- `plugins/io.github.duketopceo.pplx/bin/pplx_search.py` (modify)
- `plugins/io.github.duketopceo.pplx/bin/pplx_status.py` (modify —
  `--delete` verb)
- `plugins/io.github.duketopceo.pplx/Panel.qml` (modify — chips row,
  copy button, history delete)
- `tests/test_pplx.py` (modify)
- `plugins/io.github.duketopceo.pplx/README.md` (modify)

**Approach:**
- Helper flag allowlist (KTD4): recency chips Any/Day/Week/Month,
  context chips Low/Med/High, `-n` default 10. Unknown values → no flag.
- Result card copy action → `/usr/bin/wl-copy` detached exec, URL gated
  to `https?://` same as open; hide when binary absent.
- History row: small ✕ → `pplx_status.py --delete <index>` rewrites
  history.json atomically at 0600; panel refreshes.
- Chips state is session-only (no persistence writes).

**Test scenarios:**
- recency `week` → argv `--recency-filter week`
- context `high` → argv `--search-context-size high`
- injection-shaped values (`"week; x"`, `"../etc"`) → no flag emitted
- limit 0/21/non-int → dropped or clamped to allowlist
- `--delete` removes exactly one entry, order preserved, mode stays 0600
- copy never receives a non-http(s) URL

**Verification:** Ask with Week+High returns hits; copied URL pastes;
deleted history row stays gone across polls.

### U4. Pplx Perplexity brand pass

**Goal:** the plugin reads as a Perplexity product surface — mark, name,
honest copy — inside Omarchy theming rules.

**Requirements:** R4, R6
**Dependencies:** U3 (final UI shape to brand)
**Files:**
- `plugins/io.github.duketopceo.pplx/Panel.qml` (modify)
- `plugins/io.github.duketopceo.pplx/manifest.json` (modify — name/
  description copy)
- `plugins/io.github.duketopceo.pplx/preview.png` (regenerate)
- `plugins/io.github.duketopceo.pplx/README.md` (modify)

**Approach:**
- Glyph: magnifier nerd-font mark already in use; formalize as the brand
  tile (accent-tinted, matching bumblebee/numbat tile shape).
- Naming: manifest `name` → "Perplexity Search"; description → honest
  "Quick-ask UI for the Perplexity Search API (pplx CLI)".
- Copy: "Powered by the Perplexity Search API" footer line in the Ask
  tab; no Perplexity logo assets vendored (text mark only — logo files
  would need upstream brand permission).
- Preview card: regenerate at 1280×720 with the chips row visible.
- **Hard constraint:** zero hardcoded hex — all colors via `accentFill`/
  `fgFill`/theme (KTD6).

**Test scenarios:**
- `test_manifests` still validates the updated manifest
- QML structural check: PlainText on all Text, balanced braces
- no hex literals introduced anywhere in the plugin (grep gate)

**Verification:** panel reads as a Perplexity surface at a glance; theme
swap keeps it consistent (no baked colors to break).

### U5. Bumblebee advisory refresh

**Goal:** opt-in catalog refresh from the pinned upstream release —
visible staleness instead of silent staleness.

**Requirements:** R2, R6
**Dependencies:** none
**Files:**
- `plugins/io.github.duketopceo.bumblebee/bin/refresh_catalog.py` (new)
- `plugins/io.github.duketopceo.bumblebee/bin/scan_bumblebee.py` (modify —
  catalog source counts + refreshed_at)
- `plugins/io.github.duketopceo.bumblebee/Panel.qml` (modify — Refresh
  button + staleness line)
- `tests/test_bumblebee.py` (modify)
- `plugins/io.github.duketopceo.bumblebee/README.md` (modify)

**Approach:** per KTD5 — pinned tag + repo, HTTPS only, ~64MiB cap,
`threat_intel/` extraction only, `0.1.0` schema validation per entry,
atomic 0600 merge to `catalog.d/upstream.json`, `{ok, entries, tag,
error}` output. Panel shows "N advisories · upstream refreshed Xd ago"
and runs the helper under its own 30s deadline.

**Test scenarios:**
- success writes valid merged JSON at 0600 (fake fetch seam)
- HTTP error → `error` set, catalog.d untouched
- tarball > cap → abort, no partial write
- schema-invalid entries skipped, count honest
- catalog.d absent → created with correct modes
- `catalog_refreshed_at` reflects real file mtime

**Verification:** refresh on this machine updates the count; button
shows the timestamp.

### U6. Bumblebee service + exposure overlay

**Goal:** scan stays fresh unattended; a matched exposure interrupts.

**Requirements:** R2, R6
**Dependencies:** U5 (catalog sources in output)
**Files:**
- `plugins/io.github.duketopceo.bumblebee/Service.qml` (new)
- `plugins/io.github.duketopceo.bumblebee/Overlay.qml` (new)
- `plugins/io.github.duketopceo.bumblebee/manifest.json` (modify)
- `plugins/io.github.duketopceo.bumblebee/bin/scan_bumblebee.py` (modify —
  `age` verb for cheap staleness check)
- `tests/test_bumblebee.py` (modify)

**Approach:**
- `Service.qml`: 1h Timer → `scan_bumblebee.py age` (returns cache age
  without rescanning) → stale past 6h → `scan --force` under the helper's
  own deadline → exposure_count delta >0 → raise overlay. Watermark like
  numbat's so a restart doesn't re-alert on known exposures.
- `Overlay.qml`: urgent-styled card — "N components match known
  compromises" + top exposure name + "Open" → dropdown. Silent when clean.
- Manifest: `kinds: ["service","bar-widget","overlay"]`.

**Test scenarios:**
- `age` verb returns seconds without running a scan
- fresh cache → service does nothing
- stale cache → triggers force scan once, not repeatedly
- new exposure vs known watermark → overlay fires only on the delta
- zero exposures → silent path, no overlay state

**Verification:** age the cache, watch the service rescan and report;
inject a test exposure → popup fires.

### U7. Upstream attribution + cross-arch readiness

**Goal:** each plugin credits its upstream tool properly and documents
install on both supported arches.

**Requirements:** R5, R6, R8
**Dependencies:** none
**Files:**
- `plugins/io.github.duketopceo.{bumblebee,numbat,pplx}/UPSTREAM.md` (new ×3)
- `plugins/io.github.duketopceo.{bumblebee,numbat,pplx}/README.md` (modify)
- `plugins/io.github.duketopceo.{bumblebee,numbat,pplx}/manifest.json`
  (modify — homepage already ours; description mentions upstream tool)
- `docs/UPSTREAM.md` (modify — link the three)

**Approach:**
- `UPSTREAM.md` per plugin: tool name, `github.com/perplexityai/<repo>`
  URL, Apache-2.0 license note, install commands for **linux/amd64 and
  linux/arm64** (tarball → `~/.local/bin`), the plugin↔tool boundary
  ("wraps, does not vendor"), and a note that AUR `numbat` is the
  unrelated units language.
- README "External dependencies" section links UPSTREAM.md; keep the
  existing removal/install sections.
- Manifest description names the upstream tool plainly.

**Test scenarios:**
- every UPSTREAM.md present + referenced from README (test_manifests or
  a small docs test)
- no upstream code vendored (tree grep: no perplexityai source files)

**Verification:** a new user can install the tool on x86 or ARM from the
docs alone.

### U8. CI arch matrix + security review pass

**Goal:** the suite proves itself on both arches; a final self-review
against the marketplace round-2 checklist lands before the wave.

**Requirements:** R6, R7, R8
**Dependencies:** U1–U7 (reviews the final shape)
**Files:**
- `.github/workflows/ci.yml` (modify — add `ubuntu-24.04-arm` leg)
- `tests/` (coverage gaps found during review)
- `docs/security-review.md` or per-issue checklist comment (the review
  evidence)

**Approach:**
- CI: matrix `os: [ubuntu-latest, ubuntu-24.04-arm]` on the test job —
  helpers/tests are pure python and run identically on both; the ARM leg
  is the honest cross-arch signal for plugin code.
- Security pass: re-walk the round-2 checklist per plugin — PlainText on
  every Text, no shell, bounded I/O, O_NOFOLLOW, atomic 0600, group-kill
  deadlines, no secrets in argv/log/output, allowlisted flags, overlay
  auto-dismiss, service timer floors. Record the checklist in the plan's
  re-attestation comment.
- Grep gates: zero hex literals in QML; zero `shell=True`; no `os.system`.

**Test scenarios:**
- CI matrix green on both legs
- structural greps clean (hex, shell, PlainText counts)
- focused suites: numbat ≥15, bumblebee ≥23, pplx ≥31 after new cases

**Verification:** CI badge green on both arches; review notes posted
with the attestation.

### U9. Batch publish + consolidated re-attestation + X refresh

**Goal:** everything ships as one wave; marketplace sees one stable HEAD
per repo; launch copy reflects final surfaces.

**Requirements:** R7
**Dependencies:** U1–U8
**Files:**
- `scripts/publish.sh` (verify — no changes expected)
- `docs/launch-x-drafts.md` (refresh for live-radar + brand claims)
- marketplace issues #7322, #7323, #7324 (one comment each)

**Approach:**
- Land U1–U8 on umbrella `main`; suite green; manifests validate.
- One `publish.sh` per repo; verify standalone HEAD + fresh clone
  (manifest at root, exec bits).
- One comment per issue: final SHA + what the target now includes
  (service/overlay kinds, live events, flag allowlist, offline-by-default
  refresh, UPSTREAM.md, arch matrix) + the U8 review summary.
- Update X drafts: numbat "live radar" becomes literally true; pplx is
  branded "Perplexity Search"; remind to post on approval.

**Test scenarios:**
- full suite green; validate-manifests ok on all manifests
- fresh clone check per repo
- exactly one new comment per issue

**Verification:** standalone HEADs match attested SHAs; drafts ready.

## Scope Boundaries

**Non-goals:** enforce/blocking mode (observe-only contract stands);
`numbat ship`/HTTP export; auto-updating threat intel (opt-in only);
vendoring upstream binaries or logo assets; new plugin IDs or repo splits
(service+overlay live inside the existing plugins); pplx background work
(on-demand by design).

### Deferred to Follow-Up Work

- Preview.png regeneration with real populated panels for bumblebee/numbat
  (screenshots needed; mockups remain accurate)
- Numbat findings triage (acknowledge/suppress — needs upstream support)
- Multi-query pplx batch mode
- Per-plugin settings surfaces (manifest `settings:` schema) for cadences
  and caps — current values are sane constants

## Risks & Dependencies

- **records.ndjson may not exist even post-emit-all** until a hook fires —
  `events_live` flag + watermark handle this; tested.
- **Service/overlay review surface grows** — a persistent component is a
  bigger review target than a widget; the U8 checklist covers timer
  floors, no-left-running-process guarantees, and PlainText.
- **Upstream flag/schema drift** — allowlists and the `0.1.0` catalog
  schema are pinned to current upstream; helpers degrade rather than fail.
- **Overlay spam** — watermark + ≤3-stack queue + auto-dismiss bound the
  interrupt surface; silent-on-clean is the invariant.
- **Marketplace freeze** — U9 exists to avoid repeated review-target
  resets; no pushes between units and the wave.

## Open Questions

- Does `--emit all` at hook-install rewrite existing hook entries
  in-place? (Expected yes; rollback is a findings-only reinstall.)
- wl-copy path on stock Omarchy — `/usr/bin/wl-copy` expected; copy
  button hides when absent.
- Whether `--emit all` writes findings to records.ndjson, findings.ndjson,
  or both — merge-both logic covers all cases; dogfood confirms which.

## Sources & Research

- `numbat hook install --help`: `--emit` repeatable (findings|events|
  indicators|all); "enforce mode requires findings" — emit-all is
  monitor-mode safe.
- `numbat/docs/cli.md`: emit selection changes the default sink to
  `records.ndjson`.
- `pplx search web --help`: `--recency-filter`, `--search-context-size`,
  `-n`, `--domains`, `--published-after/before-date`, `--intent`.
- `bumblebee --help`: scan/roots/selftest/version only — refresh is
  plugin-owned.
- Multi-kind manifests verified locally: `jankeesvw.notification-center`
  (`service`+`bar-widget`), `io.github.sirjul1337.lock-explorer`
  (`service`+`overlay`, `keepLoaded:true`).
- Manifest validator (`scripts/validate-manifests.py`) accepts arbitrary
  kind keys with file existence checks.
- GitHub hosted ARM runners: `ubuntu-24.04-arm` (public repos, free).
- Live audit this session: 5,893 scan events (claude 2,727 / cursor 2,348
  / codex 829); cursor ts gap fixed at aa7978c; 24 agents wired.
