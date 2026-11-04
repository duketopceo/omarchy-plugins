# AGENTS.md — WordInk (`io.github.duketopceo.wordink`)

> Full agent context lives at: https://github.com/duketopceo/luke-agents
Inherits from luke-agents/AGENTS.md. This file specializes; it does not replace.

## What This Plugin Does

Bar widget for the WordInk dictation app: state icon, click-to-dictate, and a
panel (engine/model, mic picker, recent dictations, weekly usage, actions).
Local CLI only (`wordink ...`): no HTTP, no keys, no network.

## Provenance — edit in the umbrella, not in a published copy

Source of truth is `duketopceo/omarchy-plugins` at
`plugins/io.github.duketopceo.wordink/`; `scripts/publish.sh` subtree-pushes it
to `omarchy-wordink`. Direct commits there are overwritten.

## Layout

| Path | Role |
|---|---|
| `manifest.json` | bar-widget, category Productivity, section right |
| `Panel.qml` | icon, state machine, panel |
| `bin/wordink-cli.sh` | launcher: fixed PATH, exit 127 when `wordink` is missing |

## Runtime Contract

- `moduleName` and `ipcTarget` equal the manifest id.
- CLI contract (WordInk `apps/desktop/docs/cli.md`): exit 3 = not running; 127 (launcher) = not installed.
  `status --json` -> `capture.state` idle|recording|transcribing, `model.name`;
  `logs -f` ndjson `{"kind":"state","state":sleeping|listening|dictating|transcribing|stopping}`;
  `history --limit 3 --json` -> `entries[].final_text`; `usage --window week --json` -> `totals.{words,cost_usd}`;
  `devices` -> tab-separated name, kind, id, optional `default`.
- State: event follow while WordInk runs; 5 s `status --json` poll only when the follow is not live.
- Never add a second recording overlay. Never add network calls or key storage.
- All dynamic text is `textFormat: Text.PlainText`. Mic ids are validated before `settings set`.
- Glyphs (U+F036C/F036D/F051F/F0026) must exist in the bar font.
- Theme with `qs.Commons` `Color` / `Style` only. Bump `version` on behavior change.

## Validation

```bash
python3 scripts/validate-manifests.py
python3 scripts/check-qml-syntax.py
python3 -m pytest tests/test_wordink.py -q
omarchy plugin validate plugins/io.github.duketopceo.wordink
```

Live check: click starts/stops a dictation and the icon follows; quit WordInk and
the icon goes dim within ~5 s; click then starts the app.
