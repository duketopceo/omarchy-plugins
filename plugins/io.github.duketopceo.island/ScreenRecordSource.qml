import QtQuick 6.11
import Quickshell
import Quickshell.Io
import "ScreenRec.js" as ScreenRec

// Omarchy screen recording as an Island activity (KTD9). Follows Omarchy's own
// files and commands: the recorder's pid file in $XDG_RUNTIME_DIR is re-read
// every 2 s (no process spawn), a new pid is confirmed with
// `omarchy-capture-screenrecording --status`, and Stop runs Omarchy's
// `--stop-recording`. Elapsed time comes from the recorder's start time in
// /proc, so it is right even after a shell restart mid-recording.
Scope {
  id: src

  // The setting is on and the probe found Omarchy's recorder command.
  property bool enabled: false

  property var model: ScreenRec.initial()
  property real now: Date.now()
  readonly property var activity: ScreenRec.activity(src.model, src.now)
  readonly property string runtimeDir: Quickshell.env("XDG_RUNTIME_DIR") || ""
  // The pid last read from the file; a change triggers a status check.
  property int seenPid: 0

  onEnabledChanged: if (!src.enabled) { src.seenPid = 0; src.model = ScreenRec.initial() }

  function readPid(pid) {
    if (pid === src.seenPid) return
    src.seenPid = pid
    if (pid <= 0) { src.model = ScreenRec.initial(); return }
    src.confirm()
  }

  // A pid that changes while a check runs is checked again when it ends.
  property bool recheck: false
  function confirm() {
    if (statusProc.running) src.recheck = true
    else statusProc.running = true
  }

  function stop() {
    if (!src.model.recording) return
    Quickshell.execDetached(["omarchy-capture-screenrecording", "--stop-recording"])
  }

  FileView {
    id: pidFile
    path: src.enabled && src.runtimeDir !== "" ? src.runtimeDir + "/omarchy-screenrecord-pid" : ""
    printErrors: false
    onLoaded: src.readPid(ScreenRec.parsePid(pidFile.text()))
    onLoadFailed: src.readPid(0)
  }

  Timer {
    interval: 2000
    running: src.enabled
    repeat: true
    onTriggered: pidFile.reload()
  }

  // Exit 0: Omarchy's recorder runs under that pid. Anything else: a pid left
  // by a recording that ended without a stop, so nothing is recording.
  Process {
    id: statusProc
    command: ["omarchy-capture-screenrecording", "--status"]
    onExited: function(code) {
      if (src.recheck) { src.recheck = false; statusProc.running = true; return }
      if (code !== 0) { src.model = ScreenRec.initial(); return }
      if (src.model.recording && src.model.pid === src.seenPid) return
      startProc.recPid = src.seenPid
      if (!startProc.running) startProc.running = true
    }
  }

  // One read of the recorder's /proc start time and the uptime, per recording.
  Process {
    id: startProc
    property int recPid: 0
    command: ["/usr/bin/cat", "/proc/" + startProc.recPid + "/stat", "/proc/uptime"]
    stderr: StdioCollector {}
    stdout: StdioCollector {
      onStreamFinished: {
        var lines = String(text).split("\n")
        var secs = ScreenRec.elapsed(lines[0] || "", lines[1] || "")
        var t = Date.now()
        src.model = { recording: true, pid: startProc.recPid, startedAt: secs >= 0 ? t - secs * 1000 : t }
        src.now = t
      }
    }
  }

  // Redraw the elapsed time each second while recording, and re-confirm every
  // 15 s so a recorder that died without a stop clears.
  Timer {
    interval: 1000
    running: src.model.recording
    repeat: true
    onTriggered: src.now = Date.now()
  }
  Timer {
    interval: 15000
    running: src.model.recording
    repeat: true
    onTriggered: src.confirm()
  }
}
