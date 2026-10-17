---
title: "Hardware Nexus program roadmap"
type: feat
status: proposed
date: 2026-10-11
---

# Hardware Nexus program roadmap

Written directly (not through `ce-plan`): a one-widget plugin does not need the pipeline. Required fields (U-IDs, Now/Next/Later, status, evidence, dependencies, verification, difficulty, feasibility, simpler alternative) are all present.

**Provenance constraint.** This repo is the `git subtree split` of `duketopceo/omarchy-plugins` at `plugins/lukedaduke.nexus/`; `scripts/publish.sh` fast-forwards `main`, so direct commits here are deleted on the next publish. Every unit lands in the umbrella and arrives here by publish (U1).

**Family direction.** Design units align with the shared Omarchy-plugin direction in `duketopceo/omarchy-plugins` `DESIGN.md` once merged.

## Units

### U1. Move this docs/brand pass into the `omarchy-plugins` umbrella

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Copy to `plugins/lukedaduke.nexus/`.
- **Feasibility:** None.
- **Simpler alternative:** Mirror repo.
- **Dependencies:** none
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U2. Make the pulse conditional: run `animPulse` only while a probe is in flight, not the whole time the panel is open

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. `Panel.qml:34-41`, one `running:` binding.
- **Feasibility:** Needs an in-flight flag from the probe `Process`.
- **Simpler alternative:** Delete the pulse on the ONLINE chip; keep it only on refresh.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U3. Check the selected-tab contrast: `Color.background` text on an `accent` fill across themes

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Compute for the theme set; use an underline if any theme fails.
- **Feasibility:** Vantablack accent `#8d8d8d` on `#000` is 6.33:1, ok; light themes need a check.
- **Simpler alternative:** Underline the tab and drop the fill.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U4. Keyboard tab switching like `pplx` (`onTabRequested`)

- **Horizon:** Next
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. Reuse the `KeyboardPanel` pattern from pplx.
- **Feasibility:** None.
- **Simpler alternative:** Copy pplx's key handler, delete nothing.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U5. Replace the `preview.png` mock-up with a real capture; fix `AGENTS.md` (says ~380 lines, file is 583)

- **Horizon:** Next
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Needs a live session.
- **Feasibility:** None.
- **Simpler alternative:** Screenshot only.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U6. Fixture test for `bin/probe_nexus.py` (missing `bluetoothctl`, missing `/sys/bus/usb`)

- **Horizon:** Later
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. Fake `PATH` and a temp sysfs tree.
- **Feasibility:** None.
- **Simpler alternative:** Test the optional-probe paths only.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

