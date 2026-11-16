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

  readonly property bool micInUse: src.enabled && Privacy.micInUse(src.micRecords)
  property bool cameraInUse: false
  property var cameraApps: []

  // A mute change after the first reading, for the Island's alert.
  signal micMuteFlipped(bool muted)

  onEnabledChanged: if (!src.enabled) { src.cameraInUse = false; src.cameraApps = [] }

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
  readonly property var source: src.watchMute ? Pipewire.defaultAudioSource : null
  readonly property bool viaWpctl: Commons.UntypedInput.active
  readonly property int muteState: !src.source ? -1
    : (src.viaWpctl ? (Commons.UntypedInput.known ? (Commons.UntypedInput.muted ? 1 : 0) : -1)
                    : (src.source.audio ? (src.source.audio.muted ? 1 : 0) : -1))
  property int lastMute: -1
  onMuteStateChanged: {
    if (src.muteState < 0) { src.lastMute = -1; return }
    if (src.lastMute >= 0 && src.lastMute !== src.muteState) src.micMuteFlipped(src.muteState === 1)
    src.lastMute = src.muteState
  }
  PwObjectTracker { objects: src.source ? [src.source] : [] }

  // ---- camera in use ----
  readonly property string cameraPath: decodeURIComponent(Qt.resolvedUrl("bin/island-camera").toString().replace("file://", ""))
  Process {
    running: src.enabled
    command: [src.cameraPath, "--watch", "2"]
    stdout: SplitParser {
      onRead: function(line) {
        var r = Privacy.parseCamera(line)
        src.cameraInUse = r.inUse
        src.cameraApps = r.apps
      }
    }
  }
}
