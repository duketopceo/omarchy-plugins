import QtQuick

// The little bolt beside the charging line in the ear. Pulses while shown,
// unless motion is reduced (then it holds steady).
Text {
  id: bolt
  property bool shown: false
  property bool pulse: true
  textFormat: Text.PlainText
  text: "⚡"
  font.pixelSize: Tk.fs.bodySmall
  color: Tk.amber
  opacity: 1
  SequentialAnimation on opacity {
    running: bolt.shown && bolt.pulse && !Tk.pxl
    loops: Animation.Infinite
    NumberAnimation { to: 0.45; duration: 700; easing.type: Easing.InOutSine }
    NumberAnimation { to: 1; duration: 700; easing.type: Easing.InOutSine }
  }
}
