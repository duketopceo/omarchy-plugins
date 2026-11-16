import QtQuick 6.11
import Quickshell
import Quickshell.Io
import "Dnd.js" as Dnd

// Omarchy's Do Not Disturb state for the Island (KTD12). Reads the quiet state
// Omarchy's notification service saves, with a file watch plus a 5 s re-read
// (the service writes atomically, which can drop a watch). Toggling runs
// Omarchy's own command, which also refreshes the bar indicator. Hidden when
// the owner disabled omarchy.notifications.
Scope {
  id: src

  // The setting is on and omarchy.notifications is not disabled.
  property bool enabled: false
  // The probe found Omarchy's toggle command.
  property bool canToggle: false

  property var model: Dnd.initial()
  readonly property bool on: src.enabled && src.model.on

  // A change after the first reading: "on" or "off", for the Island's alert.
  signal toggled(string edge)

  onEnabledChanged: if (!src.enabled) src.model = Dnd.initial()

  function ingest(text) {
    var r = Dnd.step(src.model, Dnd.parse(text))
    if (r.model === src.model) return
    src.model = r.model
    if (r.edge !== "") src.toggled(r.edge)
  }

  function toggle() {
    if (src.enabled && src.canToggle) Quickshell.execDetached(["omarchy-toggle-notification-silencing"])
  }

  FileView {
    id: quietFile
    path: src.enabled ? Quickshell.env("HOME") + "/.local/state/omarchy/notifications/quiet.json" : ""
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: src.ingest(quietFile.text())
    onLoadFailed: src.ingest("")
  }

  Timer {
    interval: 5000
    running: src.enabled
    repeat: true
    onTriggered: quietFile.reload()
  }
}
