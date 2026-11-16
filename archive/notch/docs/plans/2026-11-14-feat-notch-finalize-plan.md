---
title: Notch finalize — Island ship, then wave2 and dayflow/pxl
date: 2026-11-14
type: feat
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
status: active
supersedes:
  - docs/plans/2026-11-13-feat-island-activity-merge-plan.md
  - docs/plans/2026-11-04-0215-feat-notch-island-plan.md
---

# Notch finalize — Island ship, then wave2 and dayflow/pxl

## Goal Capsule

- **Objective:** Ship the Island as the production notch surface on `main`, then land the already-written wave2 and dayflow/pxl work so features are not stranded on `local/*` branches.
- **Means:** Close PR #67 (rebase + ship blockers), then sequenced PRs that port `local/notch-wave2` and `local/notch-dayflow` onto the island tip.
- **Who finishes:** Phase A on `feature/island-activity-merge` (#67); Phase B/C on fresh branches after merge.
- **Stop conditions:** Stop Phase A if Island cannot stay the manifest entry or the dashboard Loader breaks. Do not dump wave2 into #67.

## Product Contract

Product Contract for the Island surface is unchanged from `docs/plans/2026-11-13-feat-island-activity-merge-plan.md` (R1–R6, KTD1–KTD8). This plan adds ship hygiene and follow-on feature landing.

### Scope Boundaries

**Phase A (this PR)**

- Rebase onto `main`, fix dead `omarchy-notch` URLs, theme Island via `Commons.Color`, fix stale tests, record live DoD + scorecard Asahi pass, merge #67, sync live `--link` install.

**Phase B (separate PR)**

- Settings sections + hideable/labeled tabs; clipboard (cliphist); timer/pomodoro ear; charging ear; volume/brightness HUD ownership; pinned Home actions; type-token/contrast pass.

**Phase C (separate PR after B)**

- Dayflow tab/Home/idle; pxl theme toggle; tray-hosted plugin panels; Blip unread right ear / time+date left ear.

**Out of this finalize**

- Snapdex non-default library path from island Library control; lifting duplicate `notch` IPC while dashboard Loader is open; porting Network/Power/System/Stocks into expanded island; camera calibration beyond omarchy-max defaults; merging `wip/notch-*` backup branches.

## Implementation Units

### Phase A

- **A1.** Rebase `feature/island-activity-merge` onto `origin/main`; resolve conflicts; address valid CodeRabbit items.
- **A2.** Point `manifest.json`, plugin README, catalog, and umbrella README install URLs at `https://github.com/duketopceo/omarchy-plugins`. Bump plugin version to `0.2.0`.
- **A3.** `Island.qml`: replace bare hex text/surface colors with `Commons.Color` tokens; keep dark-ink contrast readable.
- **A4.** Fix stale “old panel is retired” comment/test naming in `tests/test_notch_island.py`; run notch pytest suite.
- **A5.** Live DoD on internal screen; record Verified note in README; update `docs/reviews/io.github.duketopceo.notch.md` scorecard for Asahi/CI-assertable criteria.
- **A6.** Squash-merge #67; fast-forward live worktree to `main`; confirm `Island.qml` entry.

### Phase B / C

As in the approved Cursor plan (`notch_finalize_rewrite`): port from `local/notch-wave2` then `local/notch-dayflow` onto post-merge `main`, adapting ear features to `Island.qml` and dashboard-only pieces to the Loader dashboard.

## Success Criteria

- Live notch on omarchy-max: Island primary, dashboard secondary, no dead homepage URL.
- #67 on `main`; scorecard no longer all-pending for Asahi path.
- Wave2 + Dayflow/pxl either on `main` or closed units with green CI — not only on `local/*`.
