import QtQuick 6.11
import Quickshell
import Quickshell.Io
import Quickshell.Services.Pipewire
import qs.Commons as Commons
import "Privacy.js" as Privacy

// Mic and camera in-use indicators for the Island (KTD10), plus the default
// microphone's mute edge for the mic-mute alert. Mic: PipeWire capture streams
// that Omarchy's own bar would count (its level-meter and platform filters),
// tracked so their properties are readable, then Privacy.micInUse drops
// passive filter-chain and monitor streams. Camera: one long-running
// bin/island-camera watcher that prints a line only when the answer changes.
// Read-only.
Scope {
  id: src

  property bool enabled: false
  // The mute edge is only wanted while the Island owns the OSD's job (R6).
  property bool watchMute: false
  // Read the mute state without alerting on its edges (Home's toggle).
  property bool trackMute: false

  readonly property bool micInUse: src.enabled && Privacy.micInUse(src.micRecords)
  readonly property bool micMuted: src.muteState === 1
  property bool cameraInUse: false

  // A mute change after the first reading, for the Island's alert.
  signal micMuteFlipped(bool muted)


  // ---- microphone in use ----
  readonly property var nodes: src.enabled && Pipewire.nodes ? Pipewire.nodes.values : []
  readonly property var candidates: {
    var names = []
    for (var i = 0; i < src.nodes.length; i++) if (src.nodes[i] && src.nodes[i].name) names.push(String(src.nodes[i].name))
    var list = []
    for (var j = 0; j < src.nodes.length; j++) {
      var n = src.nodes[j]
      if (!n || !n.isStream || n.isSink !== false) continue
      if (Commons.AudioNodes.isShellLevelMeter(n.name) || Commons.AudioNodes.platformHides(n.name, names)) continue
      list.push(n)
    }
    return list
  }
  readonly property var micRecords: {
    var out = []
    for (var i = 0; i < src.candidates.length; i++) {
      var n = src.candidates[i]
      out.push({ isStream: n.isStream === true, isSink: n.isSink === true, props: n.ready && n.properties ? n.properties : {} })
    }
    return out
  }
  PwObjectTracker { objects: src.candidates }

  // ---- microphone mute edge ----
  // A virtual default source has no PwNode.audio; Omarchy reads its mute
  // through wpctl (UntypedInput), so this follows the same split as the bar.
  readonly property var source: src.watchMute || src.trackMute ? Pipewire.defaultAudioSource : null
  readonly property bool viaWpctl: Commons.UntypedInput.active
  readonly property int muteState: !src.source ? -1
    : (src.viaWpctl ? (Commons.UntypedInput.known ? (Commons.UntypedInput.muted ? 1 : 0) : -1)
                    : (src.source.audio ? (src.source.audio.muted ? 1 : 0) : -1))
  property int lastMute: -1
  // The baseline belongs to one source: switching the default microphone (a
  // headset or dock) starts a new baseline instead of reading as a mute.
  property int lastSourceId: -1
  onMuteStateChanged: {
    var id = src.source ? src.source.id : -1
    if (src.muteState < 0 || id !== src.lastSourceId) {
      src.lastSourceId = id
      src.lastMute = src.muteState
      return
    }
    if (src.watchMute && src.lastMute >= 0 && src.lastMute !== src.muteState) src.micMuteFlipped(src.muteState === 1)
    src.lastMute = src.muteState
  }
  // A switch between two sources in the same mute state changes no
  // muteState, so the new source is baselined here directly.
  onSourceChanged: {
    src.lastSourceId = src.source ? src.source.id : -1
    src.lastMute = src.muteState
  }
  PwObjectTracker { objects: src.source ? [src.source] : [] }

  // ---- camera in use ----
  readonly property string cameraPath: decodeURIComponent(Qt.resolvedUrl("bin/island-camera").toString().replace("file://", ""))
  // One long-running watcher, run by a fixed interpreter. If it exits while
  // the dots are on, its last answer is dropped and it restarts after 5 s,
  // doubling to at most 2 min, so a crash never leaves a stale dot.
  // Started and stopped explicitly (not bound): a restart after an exit
  // assigns `running`, which would silently drop a `running: enabled` binding
  // and leave the watcher on after the dots are turned off. The backoff resets
  // only after a run that lasted a minute.
  property int cameraRetryMs: 5000
  property real cameraStartedAt: 0
  function cameraStart() {
    if (!src.enabled || cameraProc.running) return
    src.cameraStartedAt = Date.now()
    cameraProc.running = true
  }
  onEnabledChanged: {
    if (src.enabled) { src.cameraRetryMs = 5000; src.cameraStart(); return }
    src.cameraInUse = false
    cameraRetry.stop()
    cameraProc.running = false
  }
  Component.onCompleted: src.cameraStart()
  Process {
    id: cameraProc
    command: ["/usr/bin/python3", src.cameraPath, "--watch", "2"]
    stdout: SplitParser {
      onRead: function(line) { src.cameraInUse = Privacy.parseCamera(line).inUse }
    }
    onExited: {
      src.cameraInUse = false
      if (!src.enabled) return
      if (Date.now() - src.cameraStartedAt >= 60000) src.cameraRetryMs = 5000
      cameraRetry.interval = src.cameraRetryMs
      src.cameraRetryMs = Math.min(120000, src.cameraRetryMs * 2)
      cameraRetry.restart()
    }
  }
  Timer {
    id: cameraRetry
    onTriggered: src.cameraStart()
  }
}
