import QtQuick
import Quickshell
import Quickshell.Io
import "Hud.js" as Hud

// Volume / brightness HUD (R6) as an ear activity (priority 95). Runs only
// when Settings > "Volume and brightness popup" is Notch (default Omarchy), so
// two popups never stack and nothing polls otherwise.
//   volume: `pactl subscribe` wakes a wpctl read on sink changes (PipeWire's
//   pulse shim ships with Omarchy); if the subscription is not up, a 600 ms poll
//   covers it.
//   brightness: the internal backlight only (brightnessctl -c backlight); the
//   kernel gives no events, so it is polled every 600 ms while a backlight
//   exists. With the lid closed and eDP-1 off the panel's value simply never
//   changes, and with no backlight or no brightnessctl nothing runs and nothing errors.
// Reads only; never writes the volume or the backlight. Activity contract:
// active, priority, text, glyph; plus kind / level / muted for the meter.
Scope {
  id: ha
  property bool enabled: false      // Settings > hudOwner === "notch"

  property var model: Hud.initial()
  property real clock: Date.now()
  property bool subOk: false
  readonly property bool hasBacklight: model.brightness !== null

  readonly property bool active: enabled && Hud.active(model, clock, "notch")
  readonly property int priority: Hud.HUD_PRIORITY
  readonly property string text: model.text
  readonly property string glyph: ""
  readonly property string kind: model.kind
  readonly property real level: model.level
  readonly property bool muted: model.muted

  onEnabledChanged: { model = Hud.initial(); if (enabled) probe.running = true }

  Timer { id: expire; onTriggered: ha.clock = Date.now() }

  function ingest(raw) {
    var now = Date.now()
    var next = Hud.step(ha.model, Hud.parseProbe(raw), now)
    ha.clock = now
    if (next === ha.model) return
    ha.model = next
    if (next.until > now) { expire.interval = next.until - now + 20; expire.restart() }
  }

  Process {
    id: probe
    command: Hud.probeArgs()
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 4000) ha.ingest(text)
    }
  }

  Timer { id: wake; interval: 50; onTriggered: if (!probe.running) probe.running = true }

  Process {
    id: sub
    running: ha.enabled
    command: ["pactl", "subscribe"]
    stdout: SplitParser {
      onRead: function (line) { ha.subOk = true; if (line.indexOf(" sink ") >= 0 || line.indexOf("'change' on server") >= 0) wake.restart() }
    }
    onExited: ha.subOk = false
  }

  Timer {
    interval: 600
    running: ha.enabled && (ha.hasBacklight || !ha.subOk)
    repeat: true
    onTriggered: if (!probe.running) probe.running = true
  }
}
