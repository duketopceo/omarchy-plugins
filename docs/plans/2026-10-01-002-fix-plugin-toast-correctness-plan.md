---
title: "Plugin toast correctness — severity gating, coalescing, cooldowns, DND"
date: 2026-10-01
type: fix
status: ready
origin: "Session audit of numbat/bumblebee/neo popup behavior after the numbat-bumblebee-neo improvements merge"
---

# Plugin toast correctness

## Problem frame

The toast surfaces in `numbat` and `bumblebee` are structurally sound (watermark-diffed, baseline-silent, capped at 3, bounded lifetime) but behaviorally wrong in ways that make them annoying:

- **Numbat toasts every fresh finding regardless of severity.** Severity only tints the card — a low/info finding produces the same overlay popup as a critical one.
- **Bursts show as up to 3 separate cards.** A batch ingest floods the corner; bumblebee already coalesces into a summary toast, numbat does not.
- **A chatty rule re-toasts indefinitely.** The watermark prevents re-toasting the *same* finding, but a rule that keeps producing *new* findings generates a new popup every poll.
- **All toasts die in 8s.** A critical finding you didn't glance at is gone — the severity signal is wasted.
- **Bumblebee can't mute a known-accepted exposure.** An exposure the user has evaluated and accepted re-toasts on every catalog-diff edge (upstream catalog adds/changes the id).
- **No plugin respects Do Not Disturb.** Toasts fire over presentations and fullscreen work.

Scope: **popup correctness only** — panel polish (badges, filters, per-unit controls) and stretch features (timeline drill-down, ship→Kurultai, neo main-browser wiring) are explicitly out of scope for this plan.

## Requirements traceability

| # | Requirement (from user ask: "less annoying popups that are more correct") | Unit |
|---|---|---|
| R1 | Low-severity findings must not popup | U1 |
| R2 | A burst must collapse to one summary toast | U2 |
| R3 | A repeating rule must not spam | U3 |
| R4 | Severity must control how long a toast lives | U4 |
| R5 | An accepted bumblebee exposure must be mutable | U5 |
| R6 | DND must suppress plugin toasts | U6 |

## Decisions

- **Settings live in the plugin's `shell.json` entry via `LocalSettings`** (`ls.entry`), matching the existing `autoCatalogRefresh` opt-out pattern in bumblebee — no new settings files.
- **Unknown/missing severity normalizes to `medium`** — preserves the current behavior for findings upstream hasn't classified; never silently drops them.
- **DND suppresses completely, watermark still advances.** Suppressed toasts do NOT replay when DND lifts — the findings remain visible in the panel. "DND means DND"; no urgent bypass (numbat findings and bumblebee exposures are ambient-alert class, not page-the-user class). If a bypass is ever wanted, bumblebee's `critical` severity is the natural seam.
- **Cooldown fingerprints `rule|agent`** at 30 min default — same rule from the same agent is one toast per half hour; different agents remain independent signals. Watermark advances regardless (panel stays truthful).
- **`notificationService` resolution copies the jankeesvw.notification-center pattern**: `shell.serviceFor(pluginRegistry.resolveEnabledId("omarchy.notifications"))` — clone-aware, null-safe. Both numbat and bumblebee Service.qml get the same resolver block.
- **No new helper processes.** All changes are in QML Service/Panel — the `.py` probes and their pytest coverage are untouched.

## Implementation units

### U1 — numbat severity gating

**Files:** `plugins/io.github.duketopceo.numbat/Service.qml`, `plugins/io.github.duketopceo.numbat/README.md`

- Add `sevRank(sev)` helper mapping `info→0, low→1, medium→2, high→3, critical→4`; unknown/empty → `medium` (2).
- Add `readonly property int toastMinRank` resolved from `ls.entry.toastMinSeverity` (string, default `"medium"`); invalid strings fall back to medium.
- In `onProbe`, filter `fresh` to `sevRank(f.severity) >= toastMinRank` before any toast append. Watermark advance (`setLastSeen(maxSeen)`) must happen regardless — filtered findings are still "seen".
- README: document `toastMinSeverity` with accepted values and the medium default.

**Test scenarios:**
- QML is not pytest-covered in this repo (suite covers `bin/*.py` only). Verification = live: seed `~/.numbat/findings.ndjson` tail with crafted records of each severity via a scratch findings file, bump watermark, watch journal for toast creation. Assert: severity below the gate produces zero toastModel appends (add a temporary `console.debug` during dev, remove before commit — or keep a `DEBUG` env-gated log line if the family has a convention; check sibling services first).
- `sevRank` pure-function review: unknown strings, empty string, `null`, numeric severities all map to a defined rank.

### U2 — numbat burst coalescing

**Files:** `plugins/io.github.duketopceo.numbat/Service.qml`

- When gated `fresh.length === 1` → single card as today. When `> 1` → ONE summary toast: `{count, topRule, topSeverity, agent}` where `topRule`/`topSeverity` come from the highest-severity fresh row (bumblebee's `enqueueToast(count, topName)` is the shape to mirror).
- Summary card text: `N new findings — worst: <rule> (<severity>)`. Click opens panel (existing behavior).
- Remove the per-row `Qt.callLater` append loop for the multi case; keep single-append for the single case.

**Test scenarios:**
- Fixture burst: 5 fresh findings → exactly 1 toastModel append, `count === 5`, top = max severity row.
- Single fresh → unchanged per-finding card.
- Burst of 10 → still 1 toast (no overflow into `_pending`; numbat has no pending queue — confirm append loop can't exceed `maxToasts`).

### U3 — numbat per-rule cooldown

**Files:** `plugins/io.github.duketopceo.numbat/Service.qml`, `plugins/io.github.duketopceo.numbat/README.md`

- `property var _ruleLastToast: ({})` — map `"rule|agent"` → epoch ms.
- Before appending any toast (single or summary), drop rows whose fingerprint toasted within `toastCooldownMs` (default 1800000, from `ls.entry.toastCooldownS`).
- If a summary toast's *top* row is cooled-down but other fresh rows aren't, summarize over the surviving rows (recount, retop).
- Update `_ruleLastToast` only for rows actually toasted.

**Test scenarios:**
- Same rule+agent twice in 30min → second produces no toast (verify via fixture re-trigger with manipulated timestamps).
- Same rule, different agent → toasts.
- Cooldown suppression does NOT block watermark advance — the finding appears in the panel.
- Map is session-only (restart resets cooldown) — acceptable; document in README.

### U4 — severity-scaled toast lifetime

**Files:** `plugins/io.github.duketopceo.numbat/Service.qml`, `plugins/io.github.duketopceo.bumblebee/Service.qml`

- Per-delegate `Timer.interval` from severity: `info/low → 6000`, `medium → 8000` (current), `high → 15000`, `critical → 0` (disabled — sticky until click). Map via the same `sevRank`.
- Bumblebee gets the same map (its toasts are all effectively `high` today — wire the delegate lifetime off the row severity even though the summary toast is uniform).
- Click behavior unchanged: numbat opens panel, bumblebee dismisses.

**Test scenarios:**
- Critical toast persists past 60s (journal/manual).
- Info toast gone by ~7s.
- Sticky toast still dismissed by click → panel open path unaffected.

### U5 — bumblebee ignore list

**Files:** `plugins/io.github.duketopceo.bumblebee/Service.qml`, `plugins/io.github.duketopceo.bumblebee/Panel.qml`, `plugins/io.github.duketopceo.bumblebee/README.md`

- `ignoredExposures` array on the plugin's shell.json entry (read via `ls.entry`, written via the existing `persist`-style read-modify-write `updateEntryInline` + `remember` pattern already used for `lastSeenExposures`).
- `diffNow` filters `pairs` through the ignore list before toasting — ignored ids still enter the persisted watermark (they're seen, just silent).
- Panel: each exposure row gets a small mute glyph (☰/bell-off — match nerd-font conventions used by sibling plugins) that appends the id to `ignoredExposures` and shows a toast-free "muted" affordance. A `muted` section or row-state in the catalog tab lists ignored ids with an unmute action.
- README documents the shell.json shape and the panel affordance.

**Test scenarios:**
- Ignore id X → next diff containing X toasts nothing, X remains in `lastSeenExposures`.
- Ignoring mid-list doesn't drop other fresh ids.
- Unmute restores toasting on the next diff edge.
- Malformed `ignoredExposures` (non-array) → treated as empty, no crash.

### U6 — DND suppression (both plugins)

**Files:** `plugins/io.github.duketopceo.numbat/Service.qml`, `plugins/io.github.duketopceo.bumblebee/Service.qml`, both READMEs

- Add the notification-service resolver (clone-aware `serviceFor`/`resolveEnabledId` pattern) and `readonly property bool dnd`.
- Gate toast append paths: while `dnd`, skip appends entirely — watermark/persist still advance so nothing replays after DND lifts.
- If `notificationService` resolves null (notification plugin disabled/uninstalled) → behave as today (fail-open: toasts show). Document.

**Test scenarios:**
- `omarchy` DND toggle on → crafted fresh finding produces zero toasts, watermark advances (second trigger produces nothing — no replay).
- DND off → toasts resume for *new* findings only.
- Notification service absent → toasts unaffected.

## Sequencing

U6 (resolver) and U1 (severity map) are independent leaf changes — do first, any order. U2 depends on U1's gate; U3 layers on U2's toast path; U4 independent. U5 independent (bumblebee-only, has its own diff path). Suggested order: U1 → U2 → U3 → U4 → U5 → U6.

## Validation

- `python3 scripts/validate-manifests.py` — unchanged (no manifest changes expected; versions bump on the *publish* step, not per-unit).
- `uv run pytest tests/ -q` — must stay green (helper code untouched).
- Live verification per unit: `omarchy-restart-shell`, seed fixture findings, watch `journalctl --user -u omarchy-shell` for the plugin's log lines. Each unit's test scenarios are the acceptance list.
- Version bumps (`numbat 0.3.0→0.3.1`, `bumblebee 0.3.0→0.3.1`) + `publish.sh` at the end — one publish covering the batch, per subtree contract.

## Risks

- **QML-only testability.** All units are QML; no automated harness exists for Service.qml in this repo. Mitigation: keep logic in small pure JS functions inside the QML, verify live against fixture files, keep the diff mechanical.
- **`notificationService` resolver is a shell-internal API** (`serviceFor`, `resolveEnabledId`). It's the same call the notification-center plugin already makes — if the shell changes it, both break together; acceptable coupling.
- **Cooldown map is session-only.** A shell restart re-arms cooled-down rules — acceptable (documented), a persistent cooldown store would add file IO for little gain.
- **ignore-list write path** reuses `updateEntryInline` — if that host API shape changes, mute silently no-ops (fail-closed toward *more* toasts, the safe direction for a security radar; note it in the panel affordance).
