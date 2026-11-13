---
title: Merge Notch activity integrations into the native Island
date: 2026-11-13
type: feature
---

# Merge Notch activity integrations into the native Island

## Goal Capsule

Replace the Notch plugin's primary dashboard presentation with the tested standalone Island direction while retaining real activity integrations and existing settings. Deliver as a reviewable plugin change; do not alter the user's live prototype automatically.

## Product Contract

R1. Use compact and expanded Island presentations, with an idle clock and date and the native prototype's camera-aware placement. Show two eligible activities when space permits, prioritizing dictation, media, agent attention, messages, and screenshots using the existing integration priorities.

R2. Expanded content is activity-focused: playback controls for media, a stop action during active dictation, a route to herdr for agents, Blip for messages, and the screenshot library for screenshots. Show actions only when their real backend is available.

R3. Do not bring network, power, system, stocks, weather, or plugin-management tabs into the Island's main flow. Existing independent widgets remain available; the old implementation and configuration remain recoverable.

R4. Keep the existing plugin ID, saved opt-in settings, monitor/cutout detection, and safe fallback on narrow or external displays. Preserve reduced-motion behavior, keyboard dismissal, and usable screen-reader labels. Never invent live data.

R5. Keep a small setup route outside the primary activity flow so new installs can explicitly enable agents, messages, and screenshots. Expose an IPC entry point that opens and focuses the Island for keyboard use; activity targets must be focusable and support Enter/Space, and Escape must dismiss without taking focus on hover.

R6. Preserve an explicit secondary route to the existing dashboard. Some deployments use `notch-slim-bar` and may otherwise lose their only configured network or finance controls. Do not alter the bar layout automatically.

## Planning Contract

- KTD1. Preserve `io.github.duketopceo.notch` as the installed ID for configuration compatibility. Implement the new UI as a separate component and leave the old panel available in source for rollback.
- KTD2. Reuse `MediaActivity.qml`, `WordinkActivity.qml`, `AgentsActivity.qml`, `MessagesActivity.qml`, `ScreenshotsActivity.qml`, `Model.js`, and `Settings.js`; do not create parallel backend collectors.
- KTD3. Use Island 0.2's compact and expanded geometry and real media presentation, not a web runtime. `Activity.js` supplies deterministic selection; the split must fit calculated screen and bar space.
- KTD4. Route unavailable integrations to an honest empty state. Existing permission and opt-in boundaries remain unchanged.
- KTD5. Keep the standalone 0.2 prototype running until the replacement has passed verification; do not install a trial as a production change without verifying it.
- KTD6. Bind each visible segment to its activity ID, not its ranking position. When the selected activity ends, close its detail view or show a neutral state; never redirect a destructive or state-changing control to a different activity. Label WordInk's toggle as Stop only while recording.
- KTD7. Render all externally sourced activity text as plain text. Preserve the existing message allowlist, automation gate, and memory-only preview behavior, and cover markup-shaped input in regression tests.
- KTD8. Keep the existing dashboard reachable through a deliberate secondary action, and allow returning to the Island. Do not assume that separate bar widgets are enabled.

## Implementation Units

### U1. Activity contract and routing

Update `plugins/io.github.duketopceo.notch/Activity.js` and `tests/test_notch_tabs.py` to choose and route eligible activities deterministically, including ties, disabled modules, unsupported actions, and narrow layouts. Test before implementation.

### U2. Native Island presentation

Add `plugins/io.github.duketopceo.notch/Island.qml` and supporting components if required. Update `manifest.json` to select it. Preserve existing collectors and settings; implement real activity-specific controls and split layout. Add tests for model, routing, geometry, and actual QML loading where feasible. Preserve all other desktop plugins.

### U3. Documentation and verification

Update `plugins/io.github.duketopceo.notch/README.md` to describe the new primary surface, integrations, recovery, and settings accurately. Run focused activity/geometry/expansion tests, manifest validation, QML parsing, and runtime checks. Verify actual pointer, keyboard, reduced-motion, media, and two-activity presentation on the internal screen; check external screen or explicitly report if unavailable.

## Verification Contract

Run the applicable `tests/test_notch_*.py` suite, `python scripts/validate-manifests.py`, `python scripts/check-qml-syntax.py`, and `git diff --check`. Exercise live QML without using production data fixtures or changing the existing desktop state. Visual verification must distinguish observed results from unavailable checks.

## Definition of Done

The plugin provides the agreed activity-focused Island without unrelated dashboard tabs; selected integrations and fallback paths work, regression checks pass, and limitations are recorded in the review. The original Notch and standalone prototype remain recoverable.
