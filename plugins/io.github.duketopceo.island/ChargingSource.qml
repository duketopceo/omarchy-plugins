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

  // The kernel refuses to read time_to_full_now unless the battery is charging,
  // so it is only read then (otherwise every poll would log a read error).
  property bool charging: false

  // Runs when the status file finishes loading: FileView.reload() is
  // asynchronous, and text() read straight after it returns the previous
  // contents (seen live with the backlight), which would make the notice one
  // poll late. Capacity and time to full were reloaded just before and are at
  // most one poll old.
  function ingest() {
    var t = Date.now()
    var status = String(statusFile.text()).trim()
    src.charging = status === "Charging"
    var reading = Charging.parse({
      status: status,
      capacity: capacityFile.text(),
      timeToFull: src.charging ? fullFile.text() : ""
    })
    src.model = Charging.step(src.model, reading, t)
    src.now = t
    if (src.activity.until > t) expire.restart()
  }

  onLiveChanged: if (!src.live) src.model = Charging.initial()

  FileView {
    id: statusFile
    path: src.live ? src.base + "status" : ""
    printErrors: false
    onLoaded: src.ingest()
  }
  FileView { id: capacityFile; path: src.live ? src.base + "capacity" : ""; blockLoading: true; printErrors: false }
  FileView { id: fullFile; path: src.live && src.charging ? src.base + "time_to_full_now" : ""; blockLoading: true; printErrors: false }

  Timer {
    interval: 5000
    running: src.live
    repeat: true
    onTriggered: {
      capacityFile.reload()
      if (src.charging) fullFile.reload()
      statusFile.reload()
    }
  }

  // Redraw once the notice has run out (6 s, one-shot).
  Timer {
    id: expire
    interval: 6100
    onTriggered: src.now = Date.now()
  }
}
