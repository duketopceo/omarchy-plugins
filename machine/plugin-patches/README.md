# Third-party plugin local changes (saved 2026-11-01)

Each plugin's full local diff was saved before updating (`<id>.full.patch`). `<id>.fixes.patch` is the same diff without the `import QtQuick 6.11` pin, which upstream and Omarchy 4.5 do not use.

| Plugin | Update | Local changes |
|---|---|---|
| akitaonrails.ai-usagebar | 1.32.0 -> 1.47.0 | The OmaSeal key wrapper is now the plugin's own `reportBinary` setting in `shell.json` (`~/.local/bin/ai-usagebar-omaseal`), so it survives updates. The height fix is obsolete (code rewritten upstream). |
| tmn73.calendar | 0.7.0 -> 0.9.2 | Import pin only; dropped. |
| crmne.hyprmoncfg | **held at 2.7.0** | 2.11.0 needs newer Omarchy shell APIs (`Commons.ShellIpc`, `paintedSize`) and fails to load on 4.0.4-mac.1. Rolled back with the full patch re-applied. Retry after the 4.5 upgrade. |
| io.github.ncr.omaphones | 1.3.13 -> 1.3.18 | Upstream fixed one of the two null checks; the other (`root && root.current`) is re-applied by hand. |
| omaplug | 1.6.6 -> 1.7.0 | Fixes re-applied cleanly. |
