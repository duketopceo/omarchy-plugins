# Review: lukedaduke.connections (omarchy-connections)
Reviewed: 7772080 · 2026-09-17 · verdict: SHIP-WITH-FIXES

## Findings

### Medium
- [MED] BarWidget.qml:58,73 — `dimmed` bindings are dead code: neither stock panel exposes `bluetoothEnabled`/`wifiEnabled` as a root property (BT panel exposes `adapter.enabled` at /usr/share/omarchy/shell/plugins/panels/bluetooth/Panel.qml:24; Wi-Fi state is `Networking.wifiEnabled` on the singleton, network/Panel.qml:140,206). `"x" in item` is always false, so the README-advertised "status-at-a-glance coloring" never dims. — Bind `item.adapter && !item.adapter.enabled` for BT and import `Quickshell.Networking` to read `Networking.wifiEnabled` for Wi-Fi.
- [MED] BarWidget.qml:14-16,19-21 — `anchorItem`/`hostWidget` injection in `injectPanels()` silently no-ops: the `Panel` base type (Ui/Panel.qml:12-19) declares neither property (only `bar`, `moduleName`, `settings`, `ipcTarget`, `manageIpc`, `controller`); `anchorItem` is a *required property of the internal KeyboardPanel* (Ui/KeyboardPanel.qml:40) and can't be retargeted post-load. Both popups stay anchored to each panel's hidden internal `BarIconButton` (bluetooth/Panel.qml:664, network/Panel.qml:980), which sits at (0,0) inside the invisible Loader — so the Wi-Fi dropdown opens under the Bluetooth icon (widget's left edge), not under the Wi-Fi icon. — Reposition the loaders to sit under their respective buttons (bind `x` to the button's x), or accept/popup-anchor at the widget edge and drop the dead injection code; don't rely on `in`-guards that mask the failure.
- [MED] BarWidget.qml:30,41 — Loading both stock panels registers duplicate `IpcHandler`s on `omarchy.bluetooth` and `omarchy.network` (bluetooth/Panel.qml:640-649, network/Panel.qml:209-223) if the user keeps the stock bar widgets enabled; first registration wins, so `qs ipc` calls route unpredictably and both panel instances run their service subscriptions. — README should tell users to disable the stock Bluetooth/Network widgets; consider a manifest conflicts note if the plugin schema supports one.

### Low
- [LOW] BarWidget.qml:30,41 — Silent degradation: if `/usr/share/omarchy/shell/plugins/panels/{bluetooth,network}/Panel.qml` is absent (non-stock install, upstream rename), the Loaders fail quietly — fallback glyphs render but clicks no-op (`if (!item) return`, lines 61,76) with no error surface. — Log a warning via `onStatusChanged`/`console.warn` or surface a broken-state tooltip when `status === Loader.Error`.
- [LOW] BarWidget.qml:27-47 — Two full panel instances stay resident for the widget's lifetime (Quickshell Bluetooth/Networking D-Bus proxies, PanelControllers, KeyboardPanel windows). Most timers/pollers are gated on `opened` so idle cost is modest, but it's heavier than two icon buttons need to be and doubles up if stock widgets also run. — Acceptable; note the tradeoff in README.

### Info
- [INFO] BarWidget.qml:30,41 — Hardcoded `file:///usr/share/omarchy/shell/plugins/panels/...` paths are package-owned and may move on an `omarchy update`; the dependency is documented in README:27-30, which is the right mitigation.
- [INFO] Security surface: the plugin itself spawns no processes, opens no sockets, writes no files, and renders no untrusted text (only static icon glyphs via `BarIconButton`→`OpticalGlyph`). All exec is inside stock Omarchy code: `execDetached` fixed-argv calls (`["omarchy-bluetooth-power", on|off]`, bluetooth/Panel.qml:637) and a shell-quoted `wl-copy` (network/Panel.qml:450). No `shell:true`-style string exec in plugin code. SSID/device-name rendering lives in the stock panels, which ship with Omarchy and are out of scope for this review.
- [INFO] Panel `settings` are not plumbed — loaded panels run with the default `settings: ({})`; plugin manifest declares no settings schema, so nothing is lost today.
- [INFO] Tests: plugin has no helpers (`bin/` absent) so there is nothing to unit-test; the manifest is covered by the umbrella `tests/test_manifests.py` schema run over `plugins/lukedaduke.connections` (identical copy, verified by `diff -r`).

## Marketplace readiness
- manifest.json: ✓ valid JSON, schemaVersion 1, id `lukedaduke.connections`, kinds `[bar-widget]`, entryPoints.barWidget → BarWidget.qml (exists); barWidget block with displayName/category/allowMultiple:false — sensible given the singleton IPC targets.
- README: ✓ install/remove commands, features, and the stock-Omarchy dependency are documented; ✗ missing the "disable stock bluetooth/network widgets" caveat (see MED-3).
- LICENSE: ✓ MIT, present.
- preview.png: ✓ valid PNG, 1280x720.

## Positives
- Zero new security surface — pure composition of already-installed stock panels; no exec/network/file code of its own.
- Defensive contract checks throughout (`"x" in item`, `typeof f === "function"`, null guards on `item`) — fails safe rather than crashing when upstream panels drift.
- Clean QML: no hardcoded colors, uses `BarIconButton`/`Style`/`qs.Commons` only.
- Full marketplace file set; umbrella copy is byte-identical to the published repo.
