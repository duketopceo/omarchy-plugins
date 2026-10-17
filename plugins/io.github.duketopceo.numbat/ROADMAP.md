# Roadmap

Program roadmap written 2026-10-11 (written directly; the `ce-plan` pipeline was skipped as too heavy
for a single-plugin repo). Design direction: [DESIGN.md](DESIGN.md).

Current state: v0.4.1. Depends on the upstream `numbat` tool (see UPSTREAM.md); upstream has no log rotation yet (README).

## Now

### U1: `dim` text meets AA on every bundled theme

- Status: Done in this PR (one property)
- Evidence: `Panel.qml` line 100 `Qt.darker(foreground, 1.5)`
- Depends on: none
- Verification: `check-qml-syntax.py` exit 0 (umbrella); manual theme swap
- **Difficulty**: easy
- **Feasibility**: none
- **Simpler alternative**: none

### U2: Severity chips: always carry a word; do not rely on colour

- Status: Check needed
- Evidence: DESIGN.md D4; `urgent` fails AA on 7 themes
- Depends on: none
- Verification: Chip text visible on miasma and solitude
- **Difficulty**: easy
- **Feasibility**: none
- **Simpler alternative**: Audit only

### U3: README screenshot (panel and toast) on a real theme

- Status: Not started
- Evidence: README has no image; preview.png exists
- Depends on: none
- Verification: Image committed
- **Difficulty**: easy: capture
- **Feasibility**: Needs a running shell and some findings (can use the fixture mode if one exists)
- **Simpler alternative**: Reuse preview.png

## Next

### U4: Replace the 50 ms repeating toast timer with an animation-driven lifetime

- Status: Known contract warning
- Evidence: `docs/PLUGIN_CONTRACT.md` lists `Service.qml` 50 ms timer as an intentional warning
- Depends on: none
- Verification: `python3 scripts/check-plugin-contract.py --strict` exit 0
- **Difficulty**: medium
- **Feasibility**: Toast fade maths must stay identical
- **Simpler alternative**: Leave the warning documented

### U5: Split `Panel.qml` (1203 lines): feed, log, jev, setup

- Status: Not started
- Evidence: File size; `Service.qml` is another 656 lines
- Depends on: none
- Verification: Screenshots identical
- **Difficulty**: medium
- **Feasibility**: Shared root properties
- **Simpler alternative**: Extract Jev tab only

### U6: Track upstream numbat releases (asset names, record formats)

- Status: Manual
- Evidence: UPSTREAM.md says "asset names vary by release"
- Depends on: none
- Verification: A smoke test runs `numbat --version` against a fixture
- **Difficulty**: medium
- **Feasibility**: Upstream format stability
- **Simpler alternative**: Pin a tested version range in UPSTREAM.md

## Later

### U7: Optional log rotation helper

- Status: Idea
- Evidence: README: numbat has no rotation yet
- Depends on: none
- Verification: n/a
- **Difficulty**: hard: the plugin is read-only by contract
- **Feasibility**: Would break the never-write rule
- **Simpler alternative**: Keep the copyable rotate command; this is the simplest answer
