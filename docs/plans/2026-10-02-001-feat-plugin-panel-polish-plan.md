# feat: Plugin panel polish — badges, filters, severity passthrough, neo controls

## Summary

Follow-up batch to the toast-correctness work (PR #22, merged `17239c06`).
Popups are now gated/coalesced/correct; this plan pulls the residual
information into the panels instead of pushing it — unseen-count badge,
severity passthrough from catalog data, per-unit neo controls — plus a
formatting-consistency pass across the three duketopceo plugins.

## Problem Frame

After the toast batch, remaining UX gaps are all panel-side:

- Numbat's bar glyph gives no count signal — you can't tell "0 new" from
  "14 new" without opening the dropdown.
- Findings rows are monochrome text; severity exists in the data but is
  invisible.
- Bumblebee treats every exposure as `high` severity for toast lifetime,
  but `catalog/exposures.json` already carries a per-entry `severity`
  field that the scanner never emits — the data is there, dropped.
- Neo's panel has restart-all only; no tab count or session identity even
  though the CDP shim exposes `/json/list` for free.
- Three plugins each grew their own `relTime`/`humanBytes`/truncation
  logic — drift already exists (e.g., two `exposureId` copies had to be
  re-synced in PR #22 review).

## Requirements

- **R1** — Numbat bar glyph shows an unseen-finding count badge (since
  last panel open), dimmed at zero, themed colors only.
- **R2** — Finding rows in the numbat feed carry a severity color chip;
  agent filter dropdown narrows the feed.
- **R3** — Bumblebee exposures carry catalog `severity` end-to-end:
  scanner emits it, service maps toast lifetime per row (replacing the
  blanket `high`), panel shows a chip. Missing severity → `high`
  (unchanged behavior).
- **R4** — Bumblebee panel shows last-scan relative age and next
  auto-refresh ETA.
- **R5** — Neo panel gains per-unit restart buttons (chromium, shim,
  server), tab count via the CDP shim's `/json/list`, and the session
  name row.
- **R6** — No new helper network calls, no writes under `~/.numbat`
  (read-only contract holds). Rotation stays hint + copyable command.
- **R7** — One shared formatting approach per plugin (no third copy of
  relTime/humanBytes); truncation consistent.

## Key Technical Decisions

- **QML-only where possible.** R1/R2/R4 are pure panel QML. R3 needs a
  scanner change (emit `severity` per exposure — additive payload key,
  backward compatible). R5 needs `tabs`/`session` in `probe_neo.py
  status` — additive.
- **Severity passthrough, not severity invention.** The catalog's own
  `severity` field is the source; upstream-refreshed catalog entries that
  lack it still default to `high`. No CVSS synthesis.
- **Tab count via HTTP, not websocket.** `GET /json/list` on the shim
  (49338) returns target list without a WS handshake; count
  `type == "page"` entries. Bounded, stdlib, same env-scrub pattern.
- **Session name**: read `name_session` state? Not exposed by claw-server
  HTTP — instead surface the MCP `instructions` server name + shim CDP
  target count; skip anything needing new server features.
- **No cross-plugin shared QML module** — plugins ship standalone
  subtrees; a shared `../common/` file would break the subtree contract.
  R7 means *identical small functions per plugin*, not a shared import.
- **Defer the rotate-now button**: executing `mv records.ndjson` breaks
  the plugin's read-only posture on `~/.numbat`. Ship a copy-to-clipboard
  affordance for the command instead (QS clipboard or `wl-copy` if the
  host exposes one — verify at implementation time; fallback: show the
  command in a selectable label).

## Implementation Units

### U1. Numbat panel — badge, chips, agent filter

**Goal:** Bar glyph gains an unseen-count badge; feed rows get severity
chips; agent dropdown filters the feed.

**Requirements:** R1, R2

**Dependencies:** none

**Files:**
- `plugins/io.github.duketopceo.numbat/Panel.qml`
- `plugins/io.github.duketopceo.numbat/manifest.json` (version bump at end of batch)
- `plugins/io.github.duketopceo.numbat/README.md`

**Approach:** Unseen count = findings with `observed_at` > the persisted
`lastPanelOpened` watermark (LocalSettings entry key, written on panel
open — same `updateEntryInline` path as the service watermark). Badge is
a small themed rect on the glyph, `visible: count > 0`. Severity chip =
tiny rounded rect + 4-char label, colored via `Color` roles
(urgent/warning/accent/dim) keyed off the same `sevRank` mapping the
service uses. Agent filter = a compact dropdown above the feed populated
from the distinct agents in the current probe payload; "all" default,
selection is panel-local (not persisted).

**Patterns to follow:** `mutedIds`/LocalSettings write-through for the
watermark; bumblebee `sevChip` component (already exists in
`Panel.qml`); the dayflow plugin's filter row if it has one.

**Test scenarios:**
- Happy: payload with mixed severities renders chips; badge shows count
  of post-watermark findings.
- Edge: zero findings → badge hidden; unknown severity → `medium` chip
  (sevRank fallback already exists).
- Edge: findings from 3 agents → filter narrows correctly, "all" restores.

**Verification:** Live: panel open shows badge reset to 0 after viewing;
re-run with a fixture record to see chips.

### U2. Numbat panel — rotation affordance

**Goal:** The existing rotation hint row gains a copyable command instead
of telling the user to type one.

**Requirements:** R6

**Dependencies:** none

**Files:**
- `plugins/io.github.duketopceo.numbat/Panel.qml`
- `plugins/io.github.duketopceo.numbat/README.md`

**Approach:** When `records_rotate_hint` is true, render the hint plus a
small "copy" button carrying the exact rotate command
(`mv ~/.numbat/records.ndjson ~/.numbat/records.ndjson.old`). Use the
host clipboard mechanism the shell already provides (check for
`Quickshell` clipboard / existing plugin copy buttons); fallback is a
`selectByMouse` text field. No file mutation from the plugin — read-only
contract stands.

**Test scenarios:**
- Happy: hint visible → button copies command (verify clipboard where
  mechanism exists; else selectable text).
- Edge: hint false → row hidden entirely.

**Verification:** Live only — needs real shell.

### U3. Bumblebee severity passthrough + scan-age rows

**Goal:** Catalog `severity` flows catalog → scanner → service → toast
lifetime/panel chip; panel shows last-scan age and next-refresh ETA.

**Requirements:** R3, R4

**Dependencies:** none

**Files:**
- `plugins/io.github.duketopceo.bumblebee/bin/scan_bumblebee.py`
- `plugins/io.github.duketopceo.bumblebee/Service.qml`
- `plugins/io.github.duketopceo.bumblebee/Panel.qml`
- `plugins/io.github.duketopceo.bumblebee/README.md`
- `tests/test_bumblebee.py`
- `plugins/io.github.duketopceo.bumblebee/manifest.json` (version bump)

**Approach:** Scanner: when an installed component matches a catalog
entry, emit `severity: <catalog severity>` on the exposure (bounded via
`_clean`, default `"high"` when absent). Service: `pairsFrom` attaches
`severity` to each pair; `enqueueToast` carries per-pair severity through
the row → `toastMsFor` already consumes it (map exists). Panel: chip per
row reusing the same component as numbat's; add "last scan Xm ago" +
"next catalog refresh in ~Nd" rows to the catalog tab (`catalog_age_s`,
`catalog_refreshed_at`, and scan-log entries already exist in the
payload).

**Patterns to follow:** `_clean`/`MAX_STR` bounding in the scanner;
existing `catalog_age_s` plumbing; numbat `toastMsFor` severity map.

**Test scenarios:**
- Happy: catalog entry `severity: "critical"` + matching installed
  component → emitted exposure carries `severity: "critical"`; service
  toast row gets sticky lifetime.
- Edge: catalog entry without severity → emitted `"high"` (default).
- Edge: refreshed upstream entries lacking severity → `high`, unchanged.
- Integration: `_exposure_ids` unchanged (id format untouched —
  severity is display metadata only, not part of the id).
- Service: mixed-severity burst → summary toast uses worst severity.

**Verification:** pytest additions in `test_bumblebee.py`; live rescan
shows per-row chips; a muted high exposure stays muted (id unchanged).

### U4. Neo panel — per-unit controls, tab count, session row

**Goal:** Per-unit restart buttons, live tab count, session/server
identity row.

**Requirements:** R5

**Dependencies:** none

**Files:**
- `plugins/io.github.duketopceo.neo/bin/probe_neo.py`
- `plugins/io.github.duketopceo.neo/Panel.qml`
- `plugins/io.github.duketopceo.neo/README.md`
- `tests/test_neo.py`
- `plugins/io.github.duketopceo.neo/manifest.json` (version bump)

**Approach:** Probe `status`: add `tabs` (count of `type=="page"`
targets from `GET http://127.0.0.1:49338/json/list`, 2s timeout, failure
→ `null` not error) and `server_name`/`server_version` from the MCP
`initialize` already performed (or `/json/version` `Browser` field).
Control verb gains `restart <unit>` per-unit: `control restart
browserclaw-chromium` — whitelist the three known units, reject others.
Panel: one restart button per unit row (existing restart-all stays),
tabs row, server identity row.

**Patterns to follow:** existing `_run` env scrub + `(rc, stdout)` tuple;
bounded urllib GET like `mcp_ok` probe; per-unit row layout already in
Panel.qml.

**Test scenarios:**
- Happy: `/json/list` returns 3 page targets → `tabs: 3`.
- Edge: shim down → `tabs: null`, panel shows `—`.
- Happy: `control restart browserclaw-shim` → rc 0 → `ok`.
- Error: `control restart bogus-unit` → rejected before systemctl runs.
- Error: systemctl nonzero → `systemctl_failed` (existing contract).

**Verification:** pytest `test_neo.py`; live restart of one unit while
watching `systemctl --user status`.

### U5. Formatting consistency pass

**Goal:** Identical `relTime`/`humanBytes`/truncation logic across the
three plugins' panels.

**Requirements:** R7

**Dependencies:** U1–U4 (touches the same files)

**Files:**
- `plugins/io.github.duketopceo.numbat/Panel.qml`
- `plugins/io.github.duketopceo.bumblebee/Panel.qml`
- `plugins/io.github.duketopceo.neo/Panel.qml`

**Approach:** Pick the best existing implementation (numbat's
`relTime`/`humanBytes` — newest), copy verbatim to the other two
plugins, align toast/row text truncation to one bound (96 chars, same as
scanner `MAX_STR`). Byte-diff the three function copies afterward — they
must be identical. No shared module (subtree contract).

**Test scenarios:** Test expectation: none — display-formatting parity,
verified by byte-identical function bodies + live spot check.

**Verification:** `diff` the three copies; grep confirms no third
variant remains.

## Scope Boundaries

- No rotate-now file mutation (read-only `~/.numbat` contract).
- No new agent-discovery or MCP work — neo probe stays local HTTP.
- No timeline drill-down / Kurultai ship / main-browser wiring (stretch
  backlog, separate plan).
- No third-party plugin changes; duketopceo-owned plugins only.

## Deferred Implementation Notes

- Clipboard mechanism for U2 is unverified — the implementer checks what
  the host/Quickshell exposes (`Quickshell` clipboard API or an existing
  plugin's copy button) and falls back to selectable text.
- Neo `name_session` state isn't exposed over HTTP today — U4 shows
  server identity + tab count instead; session name only if discovered
  reachable during implementation.
- Version bumps: one per plugin at the end covering the whole batch
  (numbat 0.3.1→0.4.0 feature, bumblebee 0.3.1→0.4.0, neo 0.1.0→0.2.0),
  then `scripts/publish.sh` for all three.

## Risks & Dependencies

- **Subtree drift**: all edits in the umbrella; publish only after the
  PR merges (provenance contract).
- **LocalSettings write race on `lastPanelOpened`**: same pattern the
  service already uses; panel writes on open are low-frequency —
  acceptable, note it in code comments.
- **`/json/list` availability**: shim serves it (it proxies CDP HTTP);
  if it 404s, `tabs` is `null` and the row degrades — fail-open by
  design.

## Sources & Research

- PR #22 review findings (merged `17239c06`): exposure-id drift lesson
  drives R7's byte-identical rule.
- `catalog/exposures.json` — `severity` key present on all 7 bundled
  entries.
- `scan_bumblebee.py` `_exposure_ids`/`_clean`/`MAX_STR` bounds.
- `probe_neo.py` — status payload, `systemctl` verbs, `/mcp` health.
- CDP shim `:49338` — `/json/version` + `/json/list` HTTP endpoints.
