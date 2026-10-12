---
title: "Bumblebee program roadmap"
type: feat
status: proposed
date: 2026-10-11
---

# Bumblebee program roadmap

Written directly (not through `ce-plan`): a one-widget plugin does not need the pipeline. Required fields (U-IDs, Now/Next/Later, status, evidence, dependencies, verification, difficulty, feasibility, simpler alternative) are all present.

**Provenance constraint.** This repo is the `git subtree split` of `duketopceo/omarchy-plugins` at `plugins/io.github.duketopceo.bumblebee/`; `scripts/publish.sh` fast-forwards `main`, so direct commits here are deleted on the next publish. Every unit lands in the umbrella and arrives here by publish (U1).

**Family direction.** Design units align with the shared Omarchy-plugin direction in `duketopceo/omarchy-plugins` `DESIGN.md` once merged.

## Units

### U1. Move this docs/brand pass into the `omarchy-plugins` umbrella so the next `publish.sh` does not delete it

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. Files only; copy to `plugins/io.github.duketopceo.bumblebee/`.
- **Feasibility:** The subtree publish is the only way files reach this repo.
- **Simpler alternative:** None: this IS the simplification. Treat this repo as a mirror.
- **Dependencies:** none
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U2. Fixture test for `bin/scan_bumblebee.py` and `refresh_catalog.py` (tar traversal, schema reject, partial scan)

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. Python stdlib `unittest`; needs tarball fixtures.
- **Feasibility:** Upstream tarball layout may change with a new `bumblebee` tag.
- **Simpler alternative:** Test only the validation functions in `refresh_catalog.py` rather than the whole scan.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U3. Add a severity word to the bar tooltip, toast and exposure rows so urgency never relies on colour

- **Horizon:** Now
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** easy. QML text change in `Panel.qml` and `Service.qml`.
- **Feasibility:** On monochrome themes (Vantablack `urgent` `#a4a4a4` vs `accent` `#8d8d8d`, 1.3:1) tint alone cannot carry state.
- **Simpler alternative:** Reuse the existing `PARTIAL` chip component for severity.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U4. Verify refreshed advisories: pin a SHA-256 of the release tarball next to the tag `v0.1.2`

- **Horizon:** Next
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. Needs the checksum computed once per bump.
- **Feasibility:** Upstream may not publish signed checksums; pin ours.
- **Simpler alternative:** Skip auto-refresh and ship the merged catalog with plugin releases (deletes ~100 lines of refresh/staleness logic).
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U5. Split `Panel.qml` (1021 lines) into one file per tab and share `accentFill`/`fgFill` with the other plugins via umbrella `shared/`

- **Horizon:** Next
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. Mechanical; QML cannot be run outside Omarchy so verify by hand.
- **Feasibility:** `qs.Ui` component loading from a plugin directory must be confirmed.
- **Simpler alternative:** The colour helpers at `Panel.qml:94-131` are copied in neo, nexus and pplx; delete four copies.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

### U6. Real README screenshot and a 10 s recording from a live session

- **Horizon:** Later
- **Status:** not started
- **Evidence:** read of `Panel.qml`/`manifest.json`/`AGENTS.md` in this repo (2026-10-11)
- **Difficulty:** medium. Needs a session with a seeded catalog entry that matches.
- **Feasibility:** Do not stage a fake exposure on a real host without cleaning up.
- **Simpler alternative:** Use the existing `catalog/exposures.json` fixture entry `ua-parser-js` in a throwaway project dir.
- **Dependencies:** U1 for where the change lands (umbrella)
- **Verification:** structural tests in the umbrella (`python3 scripts/validate-manifests.py`, `python3 -m pytest tests/`), then a manual check in a live Omarchy session; QML cannot be run outside Omarchy.

