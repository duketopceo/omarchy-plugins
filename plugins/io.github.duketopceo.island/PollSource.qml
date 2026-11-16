import QtQuick 6.11
import Quickshell
import Quickshell.Io

// Runs one read-only command and keeps its last answer. Single-flight: a
// refresh while it runs queues one more run. While `active` and `interval` > 0
// it re-runs `interval` ms after each run ends; otherwise only on refresh().
// `data` is the parsed JSON answer (null when the output is not JSON); `text`
// is the raw output.
Scope {
  id: src

  property var command: []
  property bool active: false
  property int interval: 0
  property bool json: true

  property var data: null
  property string text: ""
  property bool pending: false

  signal updated()

  function refresh() {
    if (!src.command || src.command.length === 0) return
    if (proc.running) { src.pending = true; return }
    proc.running = true
  }

  onActiveChanged: {
    if (src.active) src.refresh()
    else again.stop()
  }

  Process {
    id: proc
    command: src.command
    stdout: StdioCollector {
      onStreamFinished: {
        src.text = String(text || "")
        if (src.json) {
          var d = null
          try { d = JSON.parse(src.text) } catch (e) { d = null }
          src.data = d
        }
        src.updated()
      }
    }
    onExited: {
      if (src.pending) { src.pending = false; proc.running = true; return }
      if (src.active && src.interval > 0) again.restart()
    }
  }

  Timer {
    id: again
    interval: Math.max(500, src.interval)
    onTriggered: src.refresh()
  }
}
