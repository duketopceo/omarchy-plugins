import QtQuick
import qs.Commons as Commons

// Small dot beside the dictation text: pulses while recording, solid red on a
// mic error. `activity` is a WordinkActivity.
Rectangle {
  id: dot
  property var activity: null
  readonly property string kind: activity ? activity.state : "idle"
  width: 6; height: 6; radius: Tk.r(3)
  color: kind === "error" ? Tk.urgent : Tk.accent
  visible: kind === "recording" || kind === "error"
  SequentialAnimation on opacity {
    running: dot.kind === "recording"
    loops: Animation.Infinite
    NumberAnimation { to: 0.25; duration: 600; easing.type: Easing.InOutSine }
    NumberAnimation { to: 1.0; duration: 600; easing.type: Easing.InOutSine }
  }
}
