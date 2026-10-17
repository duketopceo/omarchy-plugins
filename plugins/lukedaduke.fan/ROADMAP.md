# Roadmap

Program roadmap written 2026-10-11 (written directly; the `ce-plan` pipeline was skipped as too heavy
for a single-plugin repo). Design direction: [DESIGN.md](DESIGN.md).

Current state: v2.5.1. Open PR #28 (`feat/fan-polish`, draft) is the card-style panel rework; #29 refreshes catalog tables. Units here do not depend on either merging.

## Now

### U1: Secondary text meets AA on every bundled theme

- Status: Done in this PR (one property)
- Evidence: `Panel.qml` line 99 used `Color.muted`; DESIGN.md D1
- Depends on: none
- Verification: `check-qml-syntax.py` exit 0 (umbrella); manual theme swap
- **Difficulty**: easy
- **Feasibility**: Merge overlap with PR #28 (two lines)
- **Simpler alternative**: none

### U2: Land or close PR #28 (card polish), keeping radius from `Style.cornerRadius`

- Status: Draft open
- Evidence: `docs/plans/2026-10-10-001-feat-fan-panel-gnome-polish-plan.md`
- Depends on: none
- Verification: Review against DESIGN.md D5
- **Difficulty**: medium: large panel diff
- **Feasibility**: Owner decision on rounded-card direction
- **Simpler alternative**: Ship the alias and kill-safety parts first and defer cards

### U3: Launch checklist: preview.png, marketplace submission, repo topics

- Status: Open items in the old roadmap
- Evidence: Earlier notes below
- Depends on: none
- Verification: Listing live
- **Difficulty**: easy
- **Feasibility**: Owner sign-off
- **Simpler alternative**: Skip the marketplace; GitHub install already works

## Next

### U4: Split `Panel.qml` (2176 lines) into section components

- Status: Not started
- Evidence: Largest QML file in the family; 30+ `root.muted` uses alone
- Depends on: U2
- Verification: Screenshots identical; syntax check exit 0
- **Difficulty**: hard: sections share one big property set and #28 touches the same lines
- **Feasibility**: Merge conflicts with #28
- **Simpler alternative**: Only extract the process list and the fan-mode block; leave the rest

### U5: Configurable temperature thresholds (from the old roadmap)

- Status: Not started
- Evidence: Old roadmap "Future work"
- Depends on: none
- Verification: Setting persists in `shell.json`; urgent tint moves
- **Difficulty**: medium
- **Feasibility**: Settings plumbing via host entry
- **Simpler alternative**: Fixed thresholds per sensor class are enough for most users

### U6: Optional sort by CPU or memory

- Status: Not started
- Evidence: Old roadmap
- Depends on: none
- Verification: Manual
- **Difficulty**: easy
- **Feasibility**: none
- **Simpler alternative**: Document `/` find as the answer

## Later

### U7: GPU utilisation percent on Apple Silicon

- Status: Blocked upstream
- Evidence: README: counters only where the driver exposes them; old roadmap says wait for asahi fdinfo
- Depends on: none
- Verification: Value appears when kernel exposes it
- **Difficulty**: hard: upstream kernel work
- **Feasibility**: Asahi kernel and driver, not in our control
- **Simpler alternative**: Keep showing power and client processes (already done)

### U8: Hibernation or AC-aware auto curve; GPU-specific curves

- Status: Not started
- Evidence: Old roadmap
- Depends on: none
- Verification: Daemon unit tests
- **Difficulty**: hard: touches the root daemon
- **Feasibility**: Safety review of any fan-curve change
- **Simpler alternative**: Skip; presets cover it

---

## Earlier notes (kept)

## Current status

Ready to install. The manifest, README, and LICENSE all pass `omarchy plugin validate`. The marketplace registry does not list it yet.

## Launch checklist

- [x] Add a clean `preview.png` (bar widget and panel)
- [ ] Submit to https://plugins.omarchy.org/publish.html
- [x] Set GitHub repo topics
- [ ] Set GitHub social preview
- [x] Add a one-line tagline to the GitHub repo description
- [ ] Write a short release note / social post

## Future work

- [ ] Deeper RAM view (pressure/PSI, per-process RSS detail)
- [ ] Better process-kill UX (filter/search, GPU-client highlighting)
- [ ] GPU utilization % once asahi fdinfo counters land in the kernel
- [ ] Configurable temperature thresholds in the bar widget
- [ ] GPU-specific fan curves
- [ ] Hibernation / AC-power-aware auto curve
- [ ] Optional process list sort by CPU or memory
- [ ] Support for more `hwmon` laptops without per-device hardcoding
