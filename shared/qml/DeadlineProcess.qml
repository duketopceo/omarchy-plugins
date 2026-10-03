import QtQuick
import Quickshell.Io

// A Process with a paired kill deadline. When the deadline passes, the whole
// process group is killed (helpers call setsid), then the direct child. Keep
// deadlineMs longer than the helper's own signal.alarm backstop.
Process {
  id: proc

  property int deadlineMs: 10000
  property bool timedOut: false

  clearEnvironment: true

  // Returns false without touching the deadline when a run is already in
  // flight, so a fast poll can never keep pushing back the kill of a hung run.
  function start() {
    if (proc.running) return false
    proc.timedOut = false
    proc.running = true
    deadline.restart()
    return true
  }

  function groupKill() {
    if (!proc.running) return
    // Quickshell exposes the pid as processId; `pid` is undefined.
    var pid = proc.processId
    if (pid > 0) {
      // A dedicated Process, not execDetached: this Quickshell rejects the
      // object form of execDetached, and the array form inherits the shell env.
      killer.command = ["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()]
      killer.running = true
    }
    proc.signal(9)
  }

  property Process killer: Process {
    clearEnvironment: true
    environment: ({ "PATH": "/usr/bin:/bin" })
  }

  onExited: deadline.stop()

  property Timer deadline: Timer {
    interval: proc.deadlineMs
    onTriggered: {
      proc.timedOut = true
      proc.groupKill()
    }
  }
}
