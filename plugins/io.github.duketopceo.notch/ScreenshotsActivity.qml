import QtQuick
import Quickshell
import Quickshell.Io
import "Screenshots.js" as Screenshots

// Flashes the caption of a newly captioned screenshot in the notch for 4 s
// (priority 30). Watches snapdex's index.md; read-only. The first read is the
// baseline, so screenshots that were already captioned never flash.
// Activity contract: active (bool), priority (int), text (string), glyph.
Scope {
  id: sa
  property bool enabled: true   // Settings > Screenshots (snapdex)

  readonly property bool active: Screenshots.isActive(model, clock)
  readonly property int priority: Screenshots.PRIORITY
  readonly property string text: model.text
  readonly property string glyph: "\u{F0100}"

  property var model: Screenshots.initial()
  property real clock: Date.now()

  Timer { id: flash; onTriggered: sa.clock = Date.now() }

  // Processed shots live in <Screenshots>/Library (index.md there); fall back
  // to the old flat index.md while the library does not exist.
  property bool libraryOk: true

  function ingest(t) {
    if (t.length > 2000000) return
    var now = Date.now()
    var next = Screenshots.step(sa.model, Screenshots.parseIndex(t), now)
    sa.clock = now
    sa.model = next
    if (next.flashUntil > now) { flash.interval = next.flashUntil - now + 20; flash.restart() }
  }

  FileView {
    path: sa.enabled ? Screenshots.libraryIndexPath(Quickshell.env("HOME")) : ""
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { sa.libraryOk = true; sa.ingest(text()) }
    onLoadFailed: sa.libraryOk = false
  }
  FileView {
    path: sa.enabled && !sa.libraryOk ? Screenshots.indexPath(Quickshell.env("HOME")) : ""
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: sa.ingest(text())
  }

  // Open the processed-shots folder from the Island's expanded view. Opens
  // nothing when the library is absent (KTD4), rather than revealing a
  // destination that is not there.
  function openLibrary() {
    var home = Quickshell.env("HOME")
    var dir = Screenshots.libraryDir(home, sa.libraryOk)
    if (dir === "") return
    Quickshell.execDetached(["/usr/bin/xdg-open", dir])
  }
}
