import QtQuick 6.11
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import "Hud.js" as Hud

// Opt-in volume/brightness HUD for the Island (KTD8). Everything that reads
// lives in a Loader that is active only while the HUD is effective (the `hud`
// setting is on and the owner disabled `omarchy.osd`), so nothing runs
// otherwise. Volume comes from PipeWire's default sink; brightness is re-read
// on each udev backlight change event. Reads only; never writes either.
Scope {
  id: src

  property bool effective: false
  // From the probe's power.backlights, e.g. "apple-panel-bl"; empty skips brightness.
  property string backlight: ""

  property var model: Hud.initial()
  property real now: Date.now()
  readonly property var activity: Hud.activity(src.model, src.now)

  function ingest(reading) {
    var t = Date.now()
    src.model = Hud.step(src.model, reading, t)
    src.now = t
    if (src.activity.until > t) expire.restart()
  }

  onEffectiveChanged: if (!src.effective) src.model = Hud.initial()

  // Redraw once the level has run out (1.6 s, one-shot).
  Timer {
    id: expire
    interval: 1700
    onTriggered: src.now = Date.now()
  }

  Loader {
    active: src.effective

    sourceComponent: Item {
      id: readers

      readonly property var sink: Pipewire.defaultAudioSink
      readonly property var audio: readers.sink && readers.sink.audio ? readers.sink.audio : null

      PwObjectTracker { objects: readers.sink ? [readers.sink] : [] }

      function readVolume() {
        if (!readers.audio || !readers.sink.ready) return
        src.ingest({ kind: "volume", value: Number(readers.audio.volume), muted: readers.audio.muted === true })
      }

      Connections {
        target: readers.audio
        function onVolumeChanged() { readers.readVolume() }
        function onMutedChanged() { readers.readVolume() }
      }
      Connections {
        target: readers.sink
        function onReadyChanged() { readers.readVolume() }
      }
      Component.onCompleted: readers.readVolume()

      // ---- backlight ----
      readonly property string base: src.backlight !== "" ? "/sys/class/backlight/" + src.backlight + "/" : ""

      // FileView.reload() loads asynchronously, so the value is read in
      // onLoaded; reading text() right after reload() returns the previous
      // contents (seen live: every level lagged one change behind). The first
      // load is the baseline (Hud.js never flashes the first reading).
      // max_brightness never changes, so it is loaded once.
      function ingestBrightness() {
        var v = parseInt(brightFile.text(), 10)
        var m = parseInt(maxFile.text(), 10)
        if (isFinite(v) && isFinite(m) && m > 0) src.ingest({ kind: "brightness", value: v, max: m })
      }

      FileView { id: maxFile; path: readers.base !== "" ? readers.base + "max_brightness" : ""; blockLoading: true; printErrors: false }
      FileView {
        id: brightFile
        path: readers.base !== "" ? readers.base + "brightness" : ""
        printErrors: false
        onLoaded: readers.ingestBrightness()
      }

      // A backlight write emits a udev "change" event on this hardware
      // (checked live on omarchy-max), so no polling is needed.
      Process {
        running: readers.base !== ""
        command: ["/usr/bin/udevadm", "monitor", "--udev", "--subsystem-match=backlight"]
        stdout: SplitParser {
          onRead: function(line) { if (line.indexOf(" change ") >= 0) brightFile.reload() }
        }
      }
    }
  }
}
