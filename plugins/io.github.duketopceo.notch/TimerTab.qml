import QtQuick
import qs.Commons as Commons
import "Timer.js" as TimerLogic

// Timer tab: a countdown (5 to 45 min) or a pomodoro (25 focus, 5 break, 15
// long break after every 4th). State and the ear text live in TimerActivity
// (`notch.timerState`); this tab only draws it and sends start / pause / cancel.
// One primary button: Start, Pause, Resume or "Start break".
Item {
  id: tab

  property var notch: null

  readonly property var ts: notch ? notch.timerState : null
  readonly property color textColor: notch ? notch.textColor : Tk.white
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""

  readonly property string st: ts ? ts.state : "idle"
  readonly property bool idle: st === "idle"
  readonly property bool pomo: ts ? (idle ? ts.pickMode === "pomodoro" : ts.model.mode === "pomodoro") : false
  readonly property real shownMs: !ts ? 0 : (idle ? (pomo ? TimerLogic.POMODORO.focus : ts.pickMinutes) * 60000 : ts.left)
  readonly property string statusText: {
    if (!ts) return ""
    if (st === "running") return pomo ? TimerLogic.phaseLabel(ts.model.phase) : "Counting down"
    if (st === "paused") return "Paused"
    if (st === "ready") return "Ready: " + TimerLogic.phaseLabel(ts.model.phase)
    return ts.active ? ts.text : (pomo ? "Focus, then a break" : "Pick a length")
  }
  readonly property string primaryText: st === "running" ? "Pause" : (st === "paused" ? "Resume" : (st === "ready" ? "Start " + TimerLogic.phaseLabel(ts.model.phase).toLowerCase() : "Start"))

  function primaryAction() {
    if (!ts) return
    if (idle) ts.start(); else ts.pauseResume()
  }

  Row {
    anchors.fill: parent
    spacing: 32

    // Readout, progress, actions.
    Column {
      width: 340
      spacing: 10
      anchors.verticalCenter: parent.verticalCenter

      Text {
        textFormat: Text.PlainText
        text: TimerLogic.fmt(tab.shownMs)
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: Tk.fs.display
        font.weight: Font.DemiBold
      }
      Text {
        width: parent.width
        textFormat: Text.PlainText
        elide: Text.ElideRight
        text: tab.statusText
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: Tk.fs.body
      }
      SegBar {
        width: parent.width
        value: tab.ts ? tab.ts.progress : 0
        fill: tab.st === "paused" ? Tk.dim : Tk.accent
      }
      Row {
        spacing: 8
        PillButton { text: tab.primaryText; primary: true; onClicked: tab.primaryAction() }
        PillButton { visible: !tab.idle; text: "Cancel"; onClicked: if (tab.ts) tab.ts.cancel() }
      }
    }

    // Choices (locked while a timer is live).
    Column {
      width: parent.width - 340 - 32
      spacing: 14
      anchors.verticalCenter: parent.verticalCenter
      enabled: tab.idle
      opacity: tab.idle ? 1 : 0.6

      Text {
        textFormat: Text.PlainText
        text: "Mode"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: Tk.fs.caption
      }
      Segmented {
        options: [{ value: "timer", label: "Timer" }, { value: "pomodoro", label: "Pomodoro" }]
        current: tab.ts ? tab.ts.pickMode : "timer"
        onPicked: function (v) { if (tab.ts) tab.ts.pickMode = v }
      }
      Text {
        textFormat: Text.PlainText
        visible: !tab.pomo
        text: "Minutes"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: Tk.fs.caption
      }
      Segmented {
        visible: !tab.pomo
        options: TimerLogic.PRESETS.map(function (m) { return { value: m, label: String(m) } })
        current: tab.ts ? tab.ts.pickMinutes : 25
        onPicked: function (v) { if (tab.ts) tab.ts.pickMinutes = v }
      }
      Text {
        visible: tab.pomo
        width: parent.width
        textFormat: Text.PlainText
        wrapMode: Text.WordWrap
        text: TimerLogic.POMODORO.focus + " min focus, " + TimerLogic.POMODORO.rest + " min break, then a " + TimerLogic.POMODORO.longRest + " min break after every " + TimerLogic.POMODORO.every + "th focus."
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: Tk.fs.bodySmall
      }
    }
  }
}
