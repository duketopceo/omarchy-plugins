import QtQuick

// Resolves a plugin's on-disk root from a component URL (pass Qt.resolvedUrl(".")
// from the plugin's entry QML). Percent-decodes, so a path with spaces or
// non-ASCII characters is usable in Process argv. Vendored from shared/qml by
// scripts/sync-shared.py; edit the shared copy, never the vendored one.
QtObject {
  id: root

  property string url: ""

  readonly property string path: {
    var p = String(root.url || "")
    if (p.indexOf("file://") === 0) p = p.substring(7)
    try { p = decodeURIComponent(p) } catch (e) {}
    while (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }
}
