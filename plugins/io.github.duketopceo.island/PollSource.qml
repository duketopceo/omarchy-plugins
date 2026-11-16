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
  // A run still going after this long is stopped, so one stalled command
  // cannot block every later refresh (single-flight).
  property int deadline: 15000

  property var data: null
  property string text: ""
  property bool pending: false

  signal updated()

  function refresh() {
    if (!src.command || src.command.length === 0) return
    if (proc.running) { src.pending = true; return }
    proc.running = true
    stall.restart()
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
        var out = String(text || "")
        // An unchanged answer reassigns nothing, so polled pages do not
        // re-evaluate every binding on each run.
        if (out === src.text && (src.data !== null || !src.json)) { src.updated(); return }
        src.text = out
        if (src.json) {
          var d = null
          try { d = JSON.parse(src.text) } catch (e) { d = null }
          src.data = d
        }
        src.updated()
      }
    }
    onExited: {
      stall.stop()
      if (src.pending) { src.pending = false; proc.running = true; stall.restart(); return }
      if (src.active && src.interval > 0) again.restart()
    }
  }

  Timer {
    id: stall
    interval: Math.max(1000, src.deadline)
    onTriggered: if (proc.running) proc.running = false
  }

  Timer {
    id: again
    interval: Math.max(500, src.interval)
    onTriggered: src.refresh()
  }
}
