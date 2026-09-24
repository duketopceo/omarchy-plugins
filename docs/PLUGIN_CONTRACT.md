# Plugin contract

Owned plugins share a small set of non-negotiable safety and reliability
properties. The contract is intentionally narrower than a full QML linter: it
catches easy-to-reintroduce trust-boundary mistakes while plugin-specific tests
cover runtime behavior.

## Required properties

- External text is bounded, validated, and rendered with
  `textFormat: Text.PlainText`.
- Helpers use fixed executable paths and explicit, minimal environments. They
  do not resolve `python3`, `sh`, or `bash` from an ambient `PATH`.
- Python helpers pass argv directly; `shell=True` and `os.system` are not
  allowed.
- Network URLs in executable code use HTTPS. Redirect targets and response
  schemas remain subject to plugin-specific validation.
- Long-lived helpers have bounded output, deadlines, and process cleanup.
  Polling work is gated by whether its surface is actually needed.
- Diagnostics never include credentials, secret values, raw tokens, or
  unbounded external payloads.
- Privileged actions use a visible authorization boundary. Stored passwords,
  `sudo -S`, and shell-string elevation are forbidden.
- Every timer below one second is either one-shot or has an explicit bounded
  UI/animation lifetime; it must not start an uncached collector.

## Running the checker

From the repository root:

```sh
python3 scripts/check-plugin-contract.py
python3 scripts/check-plugin-contract.py --format json
python3 scripts/check-plugin-contract.py --strict
```

The default command fails on errors and reports warnings. `--strict` also fails
on warnings, which is useful for a new plugin or a focused release slice.

## Current review state

The owned plugin tree currently has zero contract errors. Two intentional
warnings remain:

- `io.github.duketopceo.numbat/Service.qml` uses a 50 ms repeating timer only
  while a toast is alive; its lifetime bounds the work.
- `lukedaduke.agents/Panel.qml` uses a 280 ms single-click timer to distinguish
  single and double clicks; it does not collect data.

Third-party plugins are not silently forked into this repository. Run the
checker against a separate checkout when auditing one, then record the owner,
severity, and follow-up in `docs/reviews/active-plugin-estate.md`.
