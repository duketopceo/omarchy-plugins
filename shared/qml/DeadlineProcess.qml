import QtQuick
import Quickshell.Io

// A Process with a paired kill deadline. When the deadline passes, the whole
// process group is killed (helpers call setsid), then the direct child.
// `helperAlarmS` declares the helper's own SIGALRM backstop so the contract
// checker can assert deadlineMs > helperAlarmS * 1000.
Process {
  id: proc

  property int deadlineMs: 10000
  property int helperAlarmS: 0
  property bool timedOut: false

  clearEnvironment: true

  function start() {
    proc.timedOut = false
    proc.running = true
    deadline.restart()
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
