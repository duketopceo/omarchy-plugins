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

  FileView {
    path: sa.enabled ? Screenshots.indexPath(Quickshell.env("HOME")) : ""
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var t = text()
      if (t.length > 2000000) return
      var now = Date.now()
      var next = Screenshots.step(sa.model, Screenshots.parseIndex(t), now)
      sa.clock = now
      sa.model = next
      if (next.flashUntil > now) { flash.interval = next.flashUntil - now + 20; flash.restart() }
    }
  }
}
