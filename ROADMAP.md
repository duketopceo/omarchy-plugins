# Roadmap

Program roadmap written 2026-10-11 (written directly; the `ce-plan` pipeline was skipped as too heavy
for a single-plugin repo). Design direction: [DESIGN.md](DESIGN.md).

Catalog-level roadmap for the plugin family. Per-plugin roadmaps live in `plugins/<id>/ROADMAP.md`. Open PRs #28 (`feat/fan-polish`, draft) and #29 (`docs/refresh-plugin-tables`) are untouched by this program branch.

## Now

### U1: Adopt the Pilot Light direction (DESIGN.md) and its tokens across plugins

- Status: In this PR: fan, power, numbat text contrast fixed; standby documented exception
- Evidence: DESIGN.md audit: `muted` fails AA on 20 of 22 bundled themes
- Depends on: none
- Verification: `python3 scripts/check-qml-syntax.py` exit 0; tests exit 0
- **Difficulty**: easy: three small QML edits
- **Feasibility**: Manual theme check needs a reloadable shell
- **Simpler alternative**: none

### U2: `scripts/check-theme-contrast.py`: static guard

- Status: Not started
- Evidence: Regressions are easy: the same pattern (`Color.muted` text, Text `opacity` under 0.8) appeared in three plugins
- Depends on: U1
- Verification: Fails on a planted `Color.muted` Text; exit 0 on tree; wired into CI beside `check-plugin-contract.py`
- **Difficulty**: easy-medium: regex heuristic over QML
- **Feasibility**: Heuristic cannot see runtime colour; false positives on decorative text
- **Simpler alternative**: Add the two patterns as warnings to `check-plugin-contract.py` instead of a new script

### U3: Resolve open PRs #28 and #29

- Status: Open (#28 draft)
- Evidence: gh pr list on 2026-10-11
- Depends on: none
- Verification: Merged or closed by owner; rebase this branch if needed
- **Difficulty**: medium: #28 touches the same Panel.qml
- **Feasibility**: Owner decision
- **Simpler alternative**: Land #29 (docs) first; it is independent

## Next

### U4: Shared `dim` and `hairline` tokens in `shared/qml`

- Status: Not started
- Evidence: Each plugin defines its own (`muted` in fan, `dim` in numbat, opacities in power)
- Depends on: U1
- Verification: `sync-shared.py` copies it; consumers.txt lists plugins; syntax check exit 0
- **Difficulty**: medium: sync tooling and version bump (`shared/VERSION`)
- **Feasibility**: Qt singletons vs plain QtObject import in each plugin
- **Simpler alternative**: Keep one-line definitions per plugin; delete the idea if only three plugins use it

### U5: Theme-matrix screenshots for README and marketplace

- Status: Not started
- Evidence: No plugin README has a real screenshot
- Depends on: none
- Verification: Images for one light and one dark low-contrast theme per plugin
- **Difficulty**: hard: needs a live shell and theme swaps
- **Feasibility**: Cannot be done headless here; needs the owner machine
- **Simpler alternative**: One screenshot on the current theme per plugin

### U6: Publish brand assets to mirrors (owner-run `publish.sh`)

- Status: Blocked on merge
- Evidence: Mirrors are subtree splits; assets live at `plugins/<id>/assets/brand`
- Depends on: none
- Verification: Mirror shows the same tree
- **Difficulty**: easy for the owner
- **Feasibility**: Agents must not run `publish.sh`
- **Simpler alternative**: none

## Later

### U7: Fold the sibling-pass marks (16 px, 1.5 px stroke) and the 24-grid marks into one family sheet

- Status: Idea
- Evidence: Two grids exist: bumblebee/connections/neo/nexus/pplx use 16 px; power/fan/standby/numbat/plugins use 24
- Depends on: none
- Verification: One `assets/brand/family.svg`
- **Difficulty**: medium
- **Feasibility**: Owner sign-off on marks
- **Simpler alternative**: Leave both; they are the same grammar at two sizes
