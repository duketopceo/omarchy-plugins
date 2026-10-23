---
title: "feat: neo local-only (U17)"
type: feat
date: 2026-10-23
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
product_contract_source: docs/plans/2026-10-02-2311-feat-plugin-estate-11-of-10-plan.md
---

# feat: neo local-only (U17) - Plan

## Goal Capsule

- **Objective:** `io.github.duketopceo.neo` is honest on machines without the BrowserOS sidecar and is excluded from subtree publishing (R28).
- **Means:** catalog `localOnly` flag, drop neo from `scripts/publish.sh`, probe emits `capabilities.sidecar`, panel hides and stops polling when absent; tests cover the contract.
- **Authority:** R28 / U17 in `docs/plans/2026-10-02-2311-feat-plugin-estate-11-of-10-plan.md`; SCORECARD neo x86 waiver stays.
- **Stop conditions:** stop if Omarchy bar widgets cannot honor `visible: false` on the Panel root (verify against sibling plugins that already use `visible`).
- **Who finishes:** implementing agent via LFG; owner later archives `duketopceo/omarchy-neo` on GitHub (out of scope — needs confirmation).

## Product Contract

### Summary

Neo stays in the umbrella for Luke's machine, but `publish.sh all` must not push it, README must not present it as a marketplace install target, and the bar glyph must disappear where the three `browserclaw-*` units are not installed.

### Requirements

- R28a. `catalog.json` marks neo `localOnly: true`.
- R28b. `scripts/publish.sh` REPO map has no neo entry; `publish.sh all` and `publish.sh neo` refuse/skip.
- R28c. Retired ids (`connections`, `ticker`, `agents`) are also removed from the REPO map (U9 residual; accidental stub republish).
- R28d. When `systemctl --user show` reports all three units `LoadState=not-found`, the status payload includes `capabilities.sidecar: false`.
- R28e. When sidecar is false, `Panel.qml` sets `visible: false` and stops the 30s poll timer.
- R28f. Endpoint shown in the panel comes from the helper payload (keep a non-port placeholder default only until first status).
- R28g. README / AGENTS / umbrella README Deploy table document local-only; bump neo `manifest.json` version.

### Success Criteria

- New tests in `tests/test_neo.py` green; `publish.sh` text asserts in tests; scorecard gate still ok.
- Manual: on a machine without the units the bar shows no neo glyph (owner verify).

### Scope Boundaries

- Do not archive/privatize `duketopceo/omarchy-neo` remotely.
- Do not vendor shared VisibilityGate / `_omplug` in this unit.
- Do not change unit names, ports, or MCP endpoint constants beyond surfacing them.

### Key Technical Decisions

- KTD1. Detect absence via `LoadState=not-found` on all three units after a successful `systemctl show`. A failed `systemctl` leaves `capabilities.sidecar: true` so we never hide on probe failure. (session-settled: user-approved via U17 plan text — hide only when units do not exist.)
- KTD2. Keep neo in `catalog.json` (local inventory) with `localOnly: true` rather than removing the row — agents and install still need to find the plugin path. (session-settled: user-approved via U17 "Mark neo local-only in catalog.json".)

## Implementation Units

### U1. Catalog + publish exclusion

- **Files:** `catalog.json`, `scripts/publish.sh`, `README.md`, `tests/test_neo.py` (publish assertions), `tests/test_retirement.py` optional assert retired ids absent from publish map.
- **Approach:** Add `localOnly: true` on neo; delete neo + three retired REPO entries; update Deploy table (neo → local-only note).
- **Test scenarios:**
  - Catalog neo entry has `localOnly: true`.
  - `publish.sh` source contains no `omarchy-neo` and no retired id keys.
  - `bash -c 'source publish.sh; resolve neo'` fails.

### U2. Probe sidecar capability + panel hide

- **Files:** `plugins/io.github.duketopceo.neo/bin/probe_neo.py`, `Panel.qml`, `manifest.json`, `README.md`, `AGENTS.md`, `tests/test_neo.py`, `docs/reviews/io.github.duketopceo.neo.md` notes.
- **Approach:** Parse `LoadState` in `_unit_states`; `_status` adds `capabilities: {sidecar: bool}`; panel tracks `sidecarPresent`, binds `visible` and `statusTimer.running`.
- **Test scenarios:**
  - Fake show output with all `LoadState=not-found` → `capabilities.sidecar is False`.
  - Fake show with loaded units → `sidecar is True`.
  - Failed `_run` → `sidecar is True` (do not hide).
  - Status JSON still bounded and typed.

## Verification

```bash
python3 scripts/validate-manifests.py
python3 scripts/check-scorecard.py
python3 -m pytest tests/test_neo.py tests/test_retirement.py -q
```
