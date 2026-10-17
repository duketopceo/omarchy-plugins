---
title: "Connections program roadmap"
type: feat
status: proposed
date: 2026-10-11
---

# Connections program roadmap

Written directly (not through `ce-plan`): a one-widget plugin does not need the pipeline. Required fields (U-IDs, Now/Next/Later, status, evidence, dependencies, verification, difficulty, feasibility, simpler alternative) are all present.

**Provenance constraint.** This repo is the `git subtree split` of `duketopceo/omarchy-plugins` at `plugins/lukedaduke.connections/`; `scripts/publish.sh` fast-forwards `main`, so direct commits here are deleted on the next publish. Every unit lands in the umbrella and arrives here by publish (U1).

**Family direction.** Design units align with the shared Omarchy-plugin direction in `duketopceo/omarchy-plugins` `DESIGN.md` once merged.

## Units

### U1. Move this docs/brand pass into the `omarchy-plugins` umbrella (subtree publish deletes direct commits)

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Copy to `plugins/lukedaduke.connections/`.
- **Feasibility:** `tests/test_connections.py` parses the README for the IPC warning; keep that paragraph.
- **Simpler alternative:** None; mirror repo.
- **Dependencies:** none
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U2. Put radio state in words in the tooltips (`On`/`Off`/`No adapter`) so dimming is not the only signal

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Two string bindings in `BarWidget.qml`.
- **Feasibility:** Must keep the structural tests green (they read the QML text).
- **Simpler alternative:** Tooltip text only; no new components.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U3. Fallback icon and a one-line tooltip note if a stock panel path fails to load (today only `console.warn`)

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. `Loader.Error` branch exists; add visible state.
- **Feasibility:** Omarchy may move `/usr/share/omarchy/shell/plugins/panels/`.
- **Simpler alternative:** Reuse the existing dim state, add `Panel unavailable` to the tooltip.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U4. Drop the two full embedded stock panels by asking Omarchy for a supported way to open them without loading both

- **Horizon:** Next
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** hard. Upstream change in omacom/omarchy.
- **Feasibility:** Needs a maintainer decision.
- **Simpler alternative:** If rejected: keep as is and document the cost (already in README).
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U5. Real screenshot and recording on the dual-icon bar; replace `preview.png` mock-up

- **Horizon:** Later
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Needs a running Omarchy session with both radios.
- **Feasibility:** None.
- **Simpler alternative:** Crop a screenshot of the bar; no recording needed for a two-icon widget.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

