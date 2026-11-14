---
title: Add activity-focused island interactions to Notch
date: 2026-11-13
type: feature
---

# Add activity-focused island interactions to Notch

## Goal Capsule

Make simultaneous desktop activities visible and actionable in Notch, taking interaction ideas from IslandCN while preserving the existing Omarchy panel, cutout geometry, and optional integrations.

## Product Contract

Notch currently selects one highest-priority activity for the right ear. Dictation, media, agents, messages, and screenshots can therefore conceal each other. IslandCN demonstrates compact, split, and expanded activity presentations; it is a React library, so the implementation must be native QML rather than a direct dependency.

### Requirements

- R1. Show the two highest-priority eligible activities when space allows, with deterministic ordering and a single-activity fallback.
- R2. Keep the camera cutout clear and avoid overlap with bar widgets on internal and external displays. Constrained displays fall back to one activity.
- R3. Selecting an activity opens its existing relevant tab where available. Preserve click-to-pin, hover timing, keyboard dismissal, and first-run setup.
- R4. Animate entry, update, and exit without losing activity state. Respect reduced-motion settings.
- R5. Unavailable optional integrations remain hidden, and no placeholder action claims unsupported functionality.

### Scope Boundaries

Do not add timers, calls, uploads, or new integrations merely because IslandCN has presets. Do not replace existing tabs, change system configuration, install IslandCN, or change the default priority of existing activities.

## Planning Contract

- KTD1. Extend the existing activity contract in `plugins/io.github.duketopceo.notch/Activity.js`, not a new cross-plugin event bus. Map activity IDs to existing tabs only when those tabs are available.
- KTD2. Use an explicit space-aware fallback: show two activities only when both fit the layout; otherwise retain the current highest-priority view. Physical cutouts and virtual islands use their existing geometry paths.
- KTD3. Reuse `Motion.js`, `SpringValue.qml`, and existing theme colors. IslandCN is a design reference, not a React runtime dependency. Its repository is MIT licensed; evaluate attribution if implementation code is copied.
- KTD4. Keep hover opening Home and preserve pinned-panel state. Direct activity selection may select a tab only on deliberate activation; reopening must not reset a user-selected tab unexpectedly.

## Implementation Units

### U1. Activity selection and layout

- **Files:** `plugins/io.github.duketopceo.notch/Activity.js`, `Model.js`, `Notch.qml`; tests `tests/test_notch_model.py` and a focused activity-selection test alongside existing Notch tests.
- **Approach:** derive an ordered, bounded set of eligible activities; preserve existing single-winner behavior as fallback. Calculate available space using existing bar/cutout constraints.
- **Scenarios:** zero, one, two, and three activities; equal priorities; empty labels; disappearing integrations; narrow screen; camera cutout and virtual island; long text and bar overlap.

### U2. Activity interaction and transitions

- **Files:** `Notch.qml`, `ExpandedPanel.qml`, `Tabs.js`, `Motion.js`, and existing activity components as needed; tests `tests/test_notch_expand.py`, `tests/test_notch_tabs.py`, and relevant activity tests.
- **Approach:** expose deliberate activation per visible activity, route to existing enabled tabs, and add restrained transitions for entry, replacement, and removal. Avoid stealing keyboard focus on hover.
- **Scenarios:** activity opens the right tab; missing tab safely falls back; pin and Esc work; rapid state changes settle; reduced motion avoids spring movement; keyboard interaction has accessible labels and usable targets.

### U3. Visual validation and documentation

- **Files:** `plugins/io.github.duketopceo.notch/README.md`; existing layout and size checks in `tests/test_notch_sizes.py` and `tests/test_notch_expand.py`.
- **Approach:** validate a two-activity scenario on the laptop cutout and an external virtual island, including a narrow layout and long labels. Record actual visual results and update the activity contract documentation.
- **Scenarios:** no occluded bar content, clipped labels, focus theft, stale activity, or motion under reduced-motion settings.

## Verification Contract

Run focused existing and added pytest coverage for selection, geometry, expansion, tabs, and the affected integrations. Run `python scripts/validate-manifests.py` and `git diff --check`. On a safe development install, use `bin/notch-layout-check --expand` and inspect both internal and external displays with representative simultaneous activities. Report unavailable hardware or unverified interactions explicitly; tests alone do not establish visual quality.

## Definition of Done

Two eligible activities are visible when they fit, one remains legible when they do not, each supported activity reaches its correct tab, existing interactions and reduced-motion behavior remain intact, and the documented focused and visual checks pass.

## Appendix

- IslandCN: https://github.com/opencoredev/islandcn — activity stack, compact/split/expanded presentations, springs, and reduced motion.
- Existing baseline: `plugins/io.github.duketopceo.notch/README.md` and `docs/plans/2026-11-04-0215-feat-notch-island-plan.md`.
