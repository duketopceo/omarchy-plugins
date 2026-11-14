import QtQuick
import Quickshell
import Quickshell.Io
import "Actions.js" as Actions

// State behind the Home quick-actions row and its Settings editor (R8). The
// list is the `quickActions` setting (seeded by Settings.js). On any change
// to the list, one probe resolves which binaries exist, so a missing one shows
// disabled with a reason instead of failing silently. Toggles with a `check`
// command light up; checks run every 4 s only while Home is showing (`watch`).
Scope {
  id: st
  property var actions: []          // sanitised list from settings
  property bool watch: false        // Home visible
  property bool enabled: true

  property var found: null          // binary -> true, null while probing
  property var on: ({})             // action id -> true for lit toggles
  readonly property var items: Actions.view(actions, found)

  function byId(id) { for (var i = 0; i < actions.length; i++) if (actions[i].id === id) return actions[i]; return null }

  function run(id) {
    var a = byId(id)
    var v = null
    for (var i = 0; i < items.length; i++) if (items[i].id === id) v = items[i]
    var argv = Actions.runArgs(a)
    if (!argv || !v || !v.enabled) return
    Quickshell.execDetached(argv)
    if (a.kind === "toggle" && a.check) recheck.restart()
  }

  readonly property string bins: JSON.stringify(Actions.binaries(actions))
  onBinsChanged: { found = null; if (enabled) probe.running = true }
  Component.onCompleted: if (enabled) probe.running = true

  Process {
    id: probe
    command: Actions.probeArgs(JSON.parse(st.bins))
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: st.found = Actions.parseFound(text)
    }
  }

  // Toggle state: run each check in turn (a handful at most).
  property var queue: []
  property string current: ""
  function poll() {
    if (checker.running) return
    var q = []
    actions.forEach(function (a) { if (Actions.checkArgs(a)) q.push(a.id) })
    queue = q
    next()
  }
  function next() {
    if (queue.length === 0) { current = ""; return }
    current = queue[0]
    queue = queue.slice(1)
    var argv = Actions.checkArgs(byId(current))
    if (!argv) { next(); return }
    checker.command = argv
    checker.running = true
  }
  Process {
    id: checker
    onExited: function (code) {
      var m = {}
      for (var k in st.on) m[k] = st.on[k]
      m[st.current] = code === 0
      st.on = m
      st.next()
    }
  }
  Timer { id: recheck; interval: 700; onTriggered: st.poll() }
  Timer { interval: 4000; running: st.enabled && st.watch; repeat: true; triggeredOnStart: true; onTriggered: st.poll() }
}
