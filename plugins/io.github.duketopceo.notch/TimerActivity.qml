import QtQuick
import Quickshell
import Quickshell.Io
import "Timer.js" as TimerLogic

// The notch's timer / pomodoro (R4). Owns the model (Timer.js), ticks once a
// second while something is running or flashing, and sends exactly one desktop
// notification when a countdown (or pomodoro phase) finishes.
//   slot   ear text for the rotating idle slot while running or paused
//   active/priority/text   the "done" flash, as an ordinary activity
// TimerTab.qml drives it through start / pauseResume / cancel.
Scope {
  id: ta
  property bool enabled: true       // Settings > Timer tab

  property var model: TimerLogic.initial()
  property real clock: Date.now()
  // Choices made in the tab, kept here so they survive switching tabs.
  property string pickMode: "timer"
  property int pickMinutes: 25

  readonly property string state: model.state
  readonly property bool running: model.state === "running"
  readonly property bool inSlot: enabled && (model.state === "running" || model.state === "paused")
  readonly property string slot: inSlot ? TimerLogic.slotText(model, clock) : ""
  readonly property bool active: enabled && TimerLogic.doneActive(model, clock)
  readonly property int priority: TimerLogic.DONE_PRIORITY
  readonly property string text: model.doneText
  readonly property string glyph: ""
  readonly property real left: TimerLogic.remaining(model, clock)
  readonly property real progress: TimerLogic.progress(model, clock)

  function start() { clock = Date.now(); model = TimerLogic.start(model, pickMode, pickMinutes, clock) }
  function pauseResume() {
    clock = Date.now()
    model = model.state === "running" ? TimerLogic.pause(model, clock) : TimerLogic.resume(model, clock)
  }
  function cancel() { clock = Date.now(); model = TimerLogic.cancel(model) }

  function step() {
    var now = Date.now()
    var r = TimerLogic.tick(ta.model, now)
    ta.clock = now
    if (r.model !== ta.model) ta.model = r.model
    if (r.notify && !notifyProc.running) { notifyProc.command = TimerLogic.notifyArgs(r.notify); notifyProc.running = true }
  }
  Process { id: notifyProc }

  Timer {
    interval: 1000
    running: ta.enabled && (ta.model.state === "running" || ta.model.state === "paused" || ta.model.doneUntil > ta.clock)
    repeat: true
    onTriggered: ta.step()
  }
}
