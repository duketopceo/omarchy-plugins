# Roadmap

Program roadmap written 2026-10-11 (written directly; the `ce-plan` pipeline was skipped as too heavy
for a single-plugin repo). Design direction: [DESIGN.md](DESIGN.md).

Current state: v1.2.0, installable, passes `omarchy plugin validate`. All units below are proposals.

## Now

### U1: Secondary text meets AA on every bundled theme

- Status: Done in this PR (7 opacity literals changed)
- Evidence: `Panel.qml` lines 766, 843, 885, 928, 1036, 1082, 1120 had Text opacity 0.4 to 0.7; DESIGN.md D2
- Depends on: none
- Verification: `python3 scripts/check-qml-syntax.py` exit 0 in the umbrella; manual theme swap on a spare machine
- **Difficulty**: easy: literal change
- **Feasibility**: none
- **Simpler alternative**: none; already the smallest change

### U2: One `dim` token instead of repeated opacity literals

- Status: Not started
- Evidence: `Panel.qml` repeats `color: root.bar.foreground` with an opacity in about 10 places (grep `opacity:`)
- Depends on: none
- Verification: grep shows one definition; diff is visual no-op at 0.85
- **Difficulty**: easy: add one readonly property and replace uses
- **Feasibility**: none
- **Simpler alternative**: This is the simplification: delete the literals, keep one property

### U3: Real screenshot for README and marketplace

- Status: Not started (preview.png exists, README has no image)
- Evidence: README has no screenshot; this pass could not reload the shell
- Depends on: none
- Verification: Image shows a real theme; contrast legible
- **Difficulty**: easy: capture only
- **Feasibility**: Needs a running shell session and permission to reload it
- **Simpler alternative**: Reuse `preview.png` if it is current

## Next

### U4: Split `Panel.qml` (1131 lines) into components (hero, graph, consumers, profiles, gauge)

- Status: Not started; `component InfoLabel` already extracted
- Evidence: Single 1131-line file; `docs/reviews/active-plugin-estate.md` flags large panels
- Depends on: U2
- Verification: Behaviour-identical on screenshots; `check-qml-syntax.py` exit 0
- **Difficulty**: medium: QML component boundaries share many root properties
- **Feasibility**: Quickshell plugin loader must resolve sibling QML files (fan and numbat already ship sibling files)
- **Simpler alternative**: Leave as is and only extract `gauge` and `InfoLabel`

### U5: Keyboard path through the panel (focus ring, j/k on profiles)

- Status: Partial: `cursorActive`, `profileIndex` exist
- Evidence: `Panel.qml` properties `cursorActive`, `profileIndex`
- Depends on: none
- Verification: Manual: Tab or j/k reaches every control; focus ring uses `Style.focusBorderFor`
- **Difficulty**: medium
- **Feasibility**: Host key handling in `Panel`
- **Simpler alternative**: Document the existing keys only

## Later

### U6: Marketplace listing

- Status: Not submitted
- Evidence: README install is via `omarchy plugin add` of the GitHub URL
- Depends on: U3
- Verification: Listed on plugins.omarchy.org
- **Difficulty**: easy
- **Feasibility**: Needs owner sign-off on logo and name
- **Simpler alternative**: Stay GitHub-only
