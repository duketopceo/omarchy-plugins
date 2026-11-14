import QtQuick
import Quickshell
import Quickshell.Io
import "Dayflow.js" as Dayflow

// Dayflow work-journal state, shared by the collapsed notch, Home and the
// Dayflow tab (local customization). Polls the `dayflow` CLI only while
// `enabled` (Settings > Dayflow): status every 10 s, today's timeline every
// 60 s. The heavy reads (agents ~30 s CPU, briefing ~90 s CPU, forecast) run
// niced, one at a time, only when a visible view calls requestDetails(), and
// at most every 10 / 30 / 60 min. A missing or failing CLI just reads as
// "unavailable"; nothing here blocks the UI.
//
// Activity contract (paused capture only): active, priority, text, glyph.
Scope {
  id: df

  property bool enabled: false
  readonly property string bin: Quickshell.env("HOME") + "/.local/bin/dayflow"

  property var status: Dayflow.parseStatus("")
  property var today: Dayflow.emptyToday()
  property var agents: Dayflow.parseAgents("")
  property var briefing: Dayflow.parseBriefing("")
  property var forecast: Dayflow.parseForecast("")
  property bool toggling: false

  readonly property var act: Dayflow.activity(enabled, status)
  readonly property bool active: act.active
  readonly property int priority: act.priority
  readonly property string text: act.text
  readonly property string glyph: act.glyph
  // Idle-slot text while recording ("● Coding · 45m"); never a block title.
  readonly property string slot: enabled ? Dayflow.slotText(status, today) : ""

  function pollStatus() { if (enabled && !statusProc.running) statusProc.running = true }
  function pollToday() { if (enabled && !todayProc.running) todayProc.running = true }

  function toggle() {
    if (!enabled || toggling || !status.ok) return
    toggling = true
    toggleProc.command = Dayflow.toggleArgs(bin, status)
    toggleProc.running = true
  }

  // Heavy reads, throttled; called by the Dayflow tab while visible.
  property real agentsAt: 0
  property real briefingAt: 0
  property real forecastAt: 0
  property var queue: []
  function requestDetails() {
    if (!enabled) return
    var t = Date.now()
    var q = queue.slice()
    if (Dayflow.due(forecastAt, t, Dayflow.FORECAST_MS) && q.indexOf("forecast") < 0) { forecastAt = t; q.push("forecast") }
    if (Dayflow.due(agentsAt, t, Dayflow.AGENTS_MS) && q.indexOf("agents") < 0) { agentsAt = t; q.push("agents") }
    if (Dayflow.due(briefingAt, t, Dayflow.BRIEFING_MS) && q.indexOf("briefing") < 0) { briefingAt = t; q.push("briefing") }
    queue = q
    runNext()
  }
  function runNext() {
    if (heavyProc.running || queue.length === 0) return
    var kind = queue[0]
    queue = queue.slice(1)
    heavyProc.kind = kind
    var args = kind === "agents" ? ["agents", "--json", "--no-recaps"] : [kind, "--json"]
    heavyProc.command = ["/usr/bin/nice", "-n", "19", df.bin].concat(args)
    heavyProc.running = true
  }

  Process {
    id: statusProc
    command: [df.bin, "status", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.length < 200000) df.status = Dayflow.parseStatus(text)
    }
    onExited: function(code) { if (code !== 0) df.status = Dayflow.parseStatus("") }
  }
  Process {
    id: todayProc
    command: [df.bin, "today", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.length < 4000000) { var t = Dayflow.parseToday(text, Math.floor(Date.now() / 1000)); if (t.ok) df.today = t }
    }
  }
  Process {
    id: toggleProc
    onExited: { df.toggling = false; df.pollStatus() }
  }
  Process {
    id: heavyProc
    property string kind: ""
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (text.length > 8000000) return
        if (heavyProc.kind === "agents") { var a = Dayflow.parseAgents(text, 3); if (a.ok) df.agents = a }
        else if (heavyProc.kind === "briefing") { var b = Dayflow.parseBriefing(text, 3); if (b.ok) df.briefing = b }
        else if (heavyProc.kind === "forecast") { var f = Dayflow.parseForecast(text); if (f.ok) df.forecast = f }
      }
    }
    onExited: df.runNext()
  }

  onEnabledChanged: if (enabled) { pollStatus(); pollToday() }
  Timer { interval: Dayflow.STATUS_MS; running: df.enabled; repeat: true; triggeredOnStart: true; onTriggered: df.pollStatus() }
  Timer { interval: Dayflow.TODAY_MS; running: df.enabled; repeat: true; triggeredOnStart: true; onTriggered: df.pollToday() }
}
