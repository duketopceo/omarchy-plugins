import QtQuick
import Quickshell
import Quickshell.Io
import "Power.js" as Power

// Charging activity (R3): when AC goes in, the ear shows "62% · 1h 12m to
// full" for a few seconds (priority 60). Polls the system battery every 5 s
// (sysfs, upower as the fallback); the first reading is the baseline so a
// notch that starts on AC stays quiet. Read-only.
// Activity contract: active (bool), priority (int), text (string), glyph.
Scope {
  id: ca
  property bool enabled: true        // Settings > Charging alert
  property bool reduceMotion: false  // static bolt instead of a pulse

  readonly property bool active: enabled && Power.chargingActive(model, clock)
  readonly property int priority: Power.CHARGING_PRIORITY
  readonly property string text: model.text
  readonly property string glyph: ""   // the ChargeBolt beside the ear text draws it
  readonly property string motion: Power.chargingMotion(reduceMotion)

  property var model: Power.chargingInitial()
  property real clock: Date.now()

  Timer { id: expire; onTriggered: ca.clock = Date.now() }

  function ingest(raw) {
    var now = Date.now()
    var next = Power.chargingStep(ca.model, Power.parseBatteryProbe(raw), now)
    ca.clock = now
    if (next === ca.model) return
    ca.model = next
    if (next.until > now) { expire.interval = next.until - now + 20; expire.restart() }
  }

  Process {
    id: probe
    command: Power.batteryProbeArgs()
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 20000) ca.ingest(text)
    }
  }
  Timer {
    interval: 5000
    running: ca.enabled
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!probe.running) probe.running = true
  }
}
