---
title: Polished Dynamic Island + useful notch (public Omarchy plugin)
date: 2026-11-14
type: feat
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
supersedes:
  - docs/plans/2026-11-14-feat-notch-finalize-plan.md
---

# Polished Dynamic Island + useful notch (public Omarchy plugin)

## Goal Capsule

- **Objective:** Ship `io.github.duketopceo.notch` as a **public, installable Omarchy plugin** that looks and behaves like a polished Dynamic Island, while carrying the useful notch feature set (ears, media, timer, HUD option, tabbed dashboard, optional Dayflow/etc.), not a personal-only config dump.
- **Means:** Keep the floating pill (`IslandGeom.js`) as the compact look; morph into `ExpandedPanel` for the full tab dashboard; harden defaults and optional integrations for strangers; optionally host notifications/OSD behind an explicit opt-in that coordinates with Omarchy 4.5’s reworked notification service; publish via `scripts/publish.sh`.
- **Who finishes:** Implement on a feature branch from `main` (v0.4.1 tip); squash-merge sequenced PRs; publish standalone repo when DoD passes.
- **Stop conditions:** Stop if D-Bus notification ownership cannot be opted into safely without breaking stock Omarchy for default installs. Stop if DI compact look regresses to cutout-fill notch paint. Do not require Luke-only paths (`~/bin`, machine stash) for core features.

## Product Contract

### Actors

- **Owner** on Omarchy 4.5 + Hyprland + Quickshell (primary: Asahi MacBook with camera cutout; also external/virtual screens).
- **Other Omarchy users** installing via `omarchy plugin add` from the published standalone repo — zero prior knowledge of this umbrella tree.
- **Stock Omarchy** notification/OSD services remain the default providers unless the owner explicitly hands ownership to the island.

### Requirements

1. **R-Look:** Compact surface is a Dynamic Island pill (camera-centered capsule). Geometry lives in `IslandGeom.js` (height ~28, capped ears). Not cutout-square notch paint.
2. **R-Expand:** Hover (delay from settings) expands into the **tabbed dashboard** (`ExpandedPanel` + `Tabs.js`). Leave collapses; click pins; Esc / outside click / unfocus clears pin. Activity-only mini-card is not the primary expand target once the dashboard morph ships.
3. **R-Ears:** Compact ears show clock/date and the highest-priority live activity (media, dictation, timer, charging, HUD when owned, messages/agents when enabled), else the idle rotation (weather / watchlist / dayflow when opted in).
4. **R-Useful-core (default on for a useful notch):** Media transport in expand path; Home quick glance; Settings; System/Power/Network tabs available; timer + charging alert available; weather/stocks when data helpers succeed.
5. **R-Optional (default off or detect-gated):** Agents, Messages/Blip, Screenshots/Snapdex, Dayflow, AI usage, clipboard (cliphist), Wisp/Fan dots, HUD ownership replacing Omarchy OSD, **notification deck in the island**.
6. **R-Notifications (opt-in):** When enabled, the island may present Omarchy-class notification cards (stack/collapse/actions/theme) in or under the island morph, and must document disabling stock `omarchy.notifications` (only one `org.freedesktop.Notifications` owner). Preserve Omarchy IPC/keybind expectations where feasible (`Super+,` family). Default remains **stock Omarchy notifications** so a clean install does not steal the daemon.
7. **R-Fullscreen:** Compact island steps aside (hide or drop under FS) when the monitor has real fullscreen (Hyprland mode bit 2), matching Omarchy notification `fullscreenOn` / scanout hygiene — Overlay idle surfaces force compositing. Expand/notifications can override briefly when content is urgent (documented).
8. **R-A11y:** Keyboard open/close/tab cycle; Escape dismiss; `Commons.Style.reduceMotion` / settings reduce-motion snaps morph; no hover-only critical path; PlainText for external strings.
9. **R-Public:** Manifest/README/LICENSE; calm defaults; no hardcoded home-directory secrets; helpers under `plugins/<id>/bin/`; `Commons.Color` / `Commons.Style` theming; `scripts/publish.sh io.github.duketopceo.notch` path; release-readiness gate green.
10. **R-Multi-monitor:** One island per screen via `Variants`; primary laptop cutout uses camera width auto-detect; externals use virtual pill width.

### Acceptance examples

- Fresh `omarchy plugin add` → pill appears; hover → tabs (Home visible); leave → pill; no second notch surface; stock notifications still work until opt-in.
- Playing music → ear shows title; expand → Media tab / Home controls work.
- Fullscreen game → island not idle-Overlay blocking scanout (step-aside).
- `hudOwner: notch` + documented disable of `omarchy.osd` → volume morphs in ear without double OSD.
- Notification opt-in ON + stock service disabled → cards appear via island path; opt-in OFF → no D-Bus claim.

### Scope boundaries

**In**

- `plugins/io.github.duketopceo.notch/**`, tests, catalog/manifest version, README/AGENTS for the plugin, publish readiness.
- IslandGeom polish; ExpandedPanel morph; fullscreen step-aside; public defaults; notification **opt-in** architecture (may start as thin adapter / phased).

**Out (this program)**

- Forking/patching `/usr/share/omarchy/` notification engine into this repo.
- Replacing the Omarchy bar or lock screen.
- Cross-device sync, iOS Continuity, or non-Omarchy compositors as supported targets.
- Personal machine stash (`~/.local/share/machine/...`) as a dependency.

### Settled decisions (session)

| Decision | Choice | Rejected |
|---|---|---|
| Compact look | Dynamic Island pill (`IslandGeom`) | Cutout-fill square-top notch |
| Primary expand | Tabbed `ExpandedPanel` dashboard | Activity-only 374×180 card as end state |
| Notifications | Opt-in island host; stock default | Steal D-Bus on every install |
| Audience | Public plugin for other Omarchy users | Luke-only personal overlay |
| Ship vehicle | Umbrella → `publish.sh` standalone | Marketplace-submit the whole umbrella |

## Planning Contract

### Key technical decisions

1. **KTD1 — Single panel entry:** `manifest.entryPoints.panel = Island.qml` only. No `Notch.qml`. Namespace `omarchy-notch-island`.
2. **KTD2 — Geometry module:** All compact sizes in `IslandGeom.js` (testable). Expanded size from `Expand.panelSize` + `Tabs.sizeFor`.
3. **KTD3 — Feature gating:** Settings `feature: true` rows + runtime detection (`Capabilities.js` / probe / file existence). Missing optional deps hide UI; never crash the panel.
4. **KTD4 — Provider boundaries:** HUD and Notifications are **provider replacements**, not paint-overs. Document `disabledPlugins` entries (`omarchy.osd`, `omarchy.notifications`) when owner opts in. Mirror patterns used by community `omarchy-dynamic-island` / `omanotch`, but default safer.
5. **KTD5 — Fullscreen:** Reuse the Omarchy notifications approach: watch Hyprland events, `hasFullscreen` + mode bit 2, step aside idle Overlay to protect direct scanout.
6. **KTD6 — Open-source defaults:** Defaults favor usefulness without surprise: timer/charging/weather/stocks/media on; agents/messages/snapdex/dayflow/aiUsage/clipboard follow detect or current DEFAULTS; `hudOwner: omarchy`; notification host **false**.
7. **KTD7 — Theming:** `Theme.js` / `Tk` / `Commons.Color` only — no personal hex packs required for Swift theme.
8. **KTD8 — WIP hygiene:** Discard or fold the incomplete `feat/island-dashboard-morph` working tree into U1 cleanly; do not leave dual Island semantics.

### Research breadcrumbs

- Live Omarchy 4.5.0-3: `plugins/notifications/Service.qml` — `NotificationServer` owns D-Bus; deck top-right; fullscreen step-aside for scanout; rich cards (stack/actions/theme) per 4.5 release notes.
- Omarchy 4.5 news / releases: richer persistent notifications, DND, history, keybinds — **not** “notifications moved into notch” in first-party docs; notch docs are bar cutout awareness.
- Community: [omarchy-dynamic-island](https://github.com/Arjun010011/omarchy-dynamic-island), [omanotch](https://github.com/skuthus/omanotch) — disable stock notif/OSD then own IPC.
- Desktop DI priors: Boring Notch / NotchNook / IslandCN — compact ears, intentional expand, media+HUD+calendar usefulness, FS hide, reduced motion.
- This repo: v0.4.1 on `main` (DI pill + activity expand); tabs/`ExpandedPanel` already in tree; publish model in `docs/UPSTREAM.md`.
- OpenRouter `perplexity/sonar-pro` blocked by workspace data-region guardrails this session; research completed via Perplexity Agent API + local Omarchy source.

### Assumptions

- Omarchy plugin loader continues to inject `shell` / `manifest` and honor `keepLoaded` panels.
- Owners can edit `shell.json` `disabledPlugins` (documented in Settings hints).
- Camera width auto-detect remains good enough for 13–16" Apple panels; override stays in Advanced.

### Sequencing

U1 dashboard morph → U2 polish/FS/public README defaults → U3 notification opt-in spike → U4 publish & matrix verification.

## Implementation Units

### U1. Dashboard morph on Dynamic Island

**Outcome:** Hover/pin expand shows `ExpandedPanel` tabs while compact stays `IslandGeom` pill.

**Files:** `plugins/io.github.duketopceo.notch/Island.qml`, `IslandGeom.js`, `ExpandedPanel.qml` (wire only), `tests/test_notch_island.py`, `tests/test_island_geom.py`, manifest/catalog version.

**Approach:** Host `ExpandedPanel` in the expand morph (spring/`SpringValue` or existing Motion OPEN/CLOSE). Compact `baseWidth`/`baseHeight` from Geom — never `cut` height. Ensure root aliases tabs need (`pluginDir`, `setSetting`, `themeObj`, `textColor`, `network`, `timerState`, `capabilities`, `actionsState`, …). IPC `openTab` selects tab + expands.

**Verify:** pytest island/geom/expand/tabs; live layer `omarchy-notch-island`; hover → Home strip visible.

### U2. Polish, fullscreen step-aside, public defaults

**Outcome:** Feels intentional; safe for other users; FS-safe Overlay.

**Files:** `Island.qml` (FS watcher), `IslandGeom.js` tuning, `Settings.js` DEFAULTS/hints, `README.md`, `AGENTS.md`, tests for FS helper if extracted to JS.

**Approach:** Implement `fullscreenOn` equivalent; hide/collapse idle island under real FS. Tighten ear copy density. README: install via publish URL, settings table, optional deps, disabledPlugins recipes, screenshots. Defaults per KTD6.

**Verify:** FS game/video → island gone or non-Overlay; README install path dry-run; pytest settings defaults.

### U3. Notification / OSD opt-in (phased)

**Outcome:** Owner can move notifications (and optionally OSD) into the island without breaking default installs.

**Files:** new `NotificationsHost.qml` / thin adapter module (name TBD), Settings fields + warnings, README security/ownership section, tests for “opt-in off ⇒ no NotificationServer”.

**Approach:** Phase A — setting + UI shell that mirrors cards only when host enabled and stock plugin disabled (detect conflict, surface setup UI). Phase B — full D-Bus ownership parity only if Phase A proves stable. Prefer adapting Omarchy IPC surface over rewriting Store/Delivery wholesale. Do not vendor `/usr/share/omarchy` sources into git if license/sync cost is high — wrap or document clone-disable pattern.

**Verify:** default install unchanged; opt-in path documented with explicit disable steps; conflict warning when both claim D-Bus.

### U4. Open-source publish package

**Outcome:** Standalone repo ready for `omarchy plugin add`.

**Files:** catalog/manifest parity, LICENSE, preview assets if required by gate, `scripts/check-release-readiness.py`, `scripts/publish.sh io.github.duketopceo.notch`.

**Approach:** Run release-readiness; fix host-specific paths; publish; smoke `omarchy plugin validate` on published tree.

**Verify:** readiness exit 0; published tip has `manifest.json` at root; CI green on PR(s).

## Verification Contract

- `uvx --with pytest pytest tests/test_notch_island.py tests/test_island_geom.py tests/test_notch_expand.py tests/test_notch_tabs.py tests/test_notch_settings.py -q`
- Broader notch suite as touched: `tests/test_notch_*.py`
- `python3 scripts/validate-manifests.py`
- `python3 scripts/check-release-readiness.py` before publish
- Live on omarchy-max: single `omarchy-notch-island` layer; hover tabs; FS step-aside; stock notifications until opt-in
- CI on PR (ubuntu + arm)

## Definition of Done

- [ ] U1–U4 complete or explicitly deferred with owner sign-off (U3 Phase B may defer)
- [ ] DI pill look preserved; dashboard morph works
- [ ] Public README + calm defaults; no Luke-only hard deps for core
- [ ] Notification host default off; ownership docs correct
- [ ] Tests + CI green; version bumped; publish path exercised or scheduled
- [ ] Plan supersession noted on older finalize plan

## Appendix

### Current baseline (2026-11-14)

- `main` @ v0.4.1: DI pill + activity expand; `Notch.qml` removed; tabs present on disk.
- Working tree may hold partial `feat/island-dashboard-morph` edits — fold into U1 or reset before clean implementation.

### Considered and not built (yet)

- Always-on notification daemon steal
- Replacing Omarchy bar center with island
- Android/iOS companion
- Pixel-perfect Apple spring physics beyond Motion.js tokens
