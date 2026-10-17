---
title: "Neo program roadmap"
type: feat
status: proposed
date: 2026-10-11
---

# Neo program roadmap

Written directly (not through `ce-plan`): a one-widget plugin does not need the pipeline. Required fields (U-IDs, Now/Next/Later, status, evidence, dependencies, verification, difficulty, feasibility, simpler alternative) are all present.

**Provenance constraint.** This repo is the `git subtree split` of `duketopceo/omarchy-plugins` at `plugins/io.github.duketopceo.neo/`; `scripts/publish.sh` fast-forwards `main`, so direct commits here are deleted on the next publish. Every unit lands in the umbrella and arrives here by publish (U1).

**Family direction.** Design units align with the shared Omarchy-plugin direction in `duketopceo/omarchy-plugins` `DESIGN.md` once merged.

## Units

### U1. Move this docs/brand pass into the `omarchy-plugins` umbrella

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Copy to `plugins/io.github.duketopceo.neo/`.
- **Feasibility:** None.
- **Simpler alternative:** Mirror repo.
- **Dependencies:** none
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U2. Complete the manifest: add the `barWidget` block (displayName, category, defaultSection) and `activation` like the sibling plugins

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. JSON only; run `scripts/validate-manifests.py` in the umbrella.
- **Feasibility:** Validator may require fields the stock loader ignores.
- **Simpler alternative:** Copy the pplx manifest shape.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U3. Words with every state: `UP`/`DOWN`/`MCP silent` in the tooltip and glyph state, not tint only

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. `Panel.qml` text change.
- **Feasibility:** On light themes `dim` is `Qt.darker(fg,1.5)` and is darker than the foreground, inverting hierarchy.
- **Simpler alternative:** Replace `dim` with `Color.muted` where contrast passes, else an alpha of foreground.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U4. Unit test for `bin/probe_neo.py` with faked `systemctl` and a fake MCP server

- **Horizon:** Next
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. stdlib `http.server` fixture.
- **Feasibility:** None.
- **Simpler alternative:** Test only the JSON shaping and the `initialize` decision.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U5. Generalise unit names and ports to one constants block, still no config plumbing

- **Horizon:** Later
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. AGENTS.md forbids config plumbing; keep it to constants.
- **Feasibility:** Sidecar layout may move with BrowserOS releases.
- **Simpler alternative:** Leave hardcoded; revisit only if the layout changes.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

