import QtQuick 6.11
import Quickshell
import Quickshell.Io
import "Charging.js" as Charging

// Charging notice for the Island (KTD7). Re-reads the first battery's status,
// capacity and time to full from sysfs every 5 s; Charging.js decides when a
// reading is a fresh plug-in. Read-only.
Scope {
  id: src

  property bool enabled: false
  // From the probe's power.batteries, e.g. "macsmc-battery"; empty hides the activity.
  property string battery: ""

  property var model: Charging.initial()
  property real now: Date.now()
  readonly property bool live: src.enabled && src.battery !== ""
  readonly property var activity: Charging.activity(src.model, src.now)
  readonly property string base: "/sys/class/power_supply/" + src.battery + "/"

  // Raw time_to_full_now text, read once per plug-in. The kernel refuses that
  // read unless it currently reports Charging (it flips to "Not charging" at
  // the charge limit), and FileView logs every refused read even with
  // printErrors off, so it is read by a one-shot process with stderr dropped.
  property string timeToFull: ""

  // Runs when the status file finishes loading: FileView.reload() is
  // asynchronous, and text() read straight after it returns the previous
  // contents (seen live with the backlight), which would make the notice one
  // poll late. Capacity was reloaded just before and is at most one poll old.
  function ingest() {
    var t = Date.now()
    var status = String(statusFile.text()).trim()
    if (status !== "Charging") src.timeToFull = ""
    var reading = Charging.parse({ status: status, capacity: capacityFile.text(), timeToFull: src.timeToFull })
    var next = Charging.step(src.model, reading, t)
    // An unchanged reading returns the same model: write nothing, so an idle
    // battery polled every 5 s redraws nothing. The expire timer redraws when
    // a notice runs out.
    if (next === src.model) return
    // Re-arm the redraw only for a new notice: a later reading must not push
    // the redraw past the notice's end.
    var fresh = next.until !== src.model.until
    src.model = next
    src.now = t
    if (fresh && next.until > t) {
      expire.restart()
      // The alert waits for the time-to-full read so it can say "to full";
      // fullProc emits it once, whether the read succeeds or not.
      src.alertPending = true
      if (!fullProc.running) fullProc.running = true
    }
  }

  // A fresh plug-in notice, for the Island's charging alert.
  signal charged(var model)
  property bool alertPending: false
  function emitPending() {
    if (!src.alertPending) return
    src.alertPending = false
    src.charged(src.model)
  }

  onLiveChanged: if (!src.live) src.model = Charging.initial()

  FileView {
    id: statusFile
    path: src.live ? src.base + "status" : ""
    printErrors: false
    onLoaded: src.ingest()
  }
  FileView { id: capacityFile; path: src.live ? src.base + "capacity" : ""; blockLoading: true; printErrors: false }

  Process {
    id: fullProc
    command: ["/usr/bin/cat", src.base + "time_to_full_now"]
    stderr: StdioCollector {}
    stdout: StdioCollector {
      onStreamFinished: {
        src.timeToFull = String(text).trim()
        var next = Charging.step(src.model, Charging.parse({
          status: src.model.status, capacity: String(src.model.capacity), timeToFull: src.timeToFull
        }), Date.now())
        if (next !== src.model) src.model = next
        src.emitPending()
      }
    }
    // A refused or failed read still sends the alert, with the percent only.
    onExited: src.emitPending()
  }

  Timer {
    interval: 5000
    running: src.live
    repeat: true
    onTriggered: {
      capacityFile.reload()
      statusFile.reload()
    }
  }

  // Redraw once the notice has run out (one-shot).
  Timer {
    id: expire
    interval: Charging.NOTICE_MS + 100
    onTriggered: src.now = Date.now()
  }
}
