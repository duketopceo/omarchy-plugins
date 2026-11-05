import QtQuick
import Quickshell
import Quickshell.Io
import "Agents.js" as Agents

// Coding-agent status from the herdr desktop app. Follows `herdr-core events`
// (JSON lines, one per change) as a trigger and re-reads `herdr-app ls` (the
// space/tab/terminal grouping the events lack); a 10 s poll covers a stream
// that ended or a window that opened later. Read-only.
//
// Activity contract: active (bool), priority (int), text (string), glyph.
Scope {
  id: ag

  property var summary: Agents.parseLs("")
  readonly property bool active: Agents.isActive(summary)
  readonly property int priority: Agents.priority(summary)
  readonly property string text: Agents.activityText(summary)
  readonly property string glyph: Agents.glyph(summary)
  // Idle-notch badge: "● 3" while agents are working, "" otherwise.
  readonly property string badge: Agents.badgeText(summary)
  readonly property int workingCount: summary.counts.working

  readonly property string appBin: Quickshell.env("HOME") + "/.local/bin/herdr-app"
  readonly property string coreBin: Quickshell.env("HOME") + "/.local/bin/herdr-core"

  function poll() { if (!lsProc.running) lsProc.running = true }

  Process {
    id: lsProc
    command: [ag.appBin, "ls"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 2000000) ag.summary = Agents.parseLs(text)
    }
    // App closed or not installed: no agents to show.
    onExited: function(code) { if (code !== 0) ag.summary = Agents.parseLs("") }
  }

  // Events are only a "something changed" signal; debounce bursts.
  Timer { id: debounce; interval: 400; onTriggered: ag.poll() }

  Process {
    id: follow
    command: [ag.coreBin, "events", "--json"]
    stdout: SplitParser {
      splitMarker: "\n"
      onRead: function(line) { debounce.restart() }
    }
    onExited: restartFollow.start()
  }
  Timer { id: restartFollow; interval: 15000; onTriggered: follow.running = true }
  Component.onCompleted: follow.running = true

  Timer {
    interval: 10000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: ag.poll()
  }
}
