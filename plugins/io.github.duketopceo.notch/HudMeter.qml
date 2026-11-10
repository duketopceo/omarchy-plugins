import QtQuick

// The small level meter beside the HUD text in the ear: a track and a fill.
// Muted draws an empty track. Fill is the accent (urgent never: a quiet
// volume is not an alert); width follows `level` without animation so it
// tracks held keys exactly.
Item {
  id: meter
  property real level: 0     // 0..100
  property bool muted: false
  implicitWidth: 36
  implicitHeight: 6
  width: implicitWidth
  height: implicitHeight
  Rectangle {
    anchors.fill: parent
    radius: Tk.r(height / 2)
    color: Tk.tint(0.2)
  }
  Rectangle {
    width: meter.muted ? 0 : Math.max(meter.height, meter.width * Math.max(0, Math.min(100, meter.level)) / 100)
    visible: !meter.muted && meter.level > 0
    height: parent.height
    radius: Tk.r(height / 2)
    color: Tk.accent
  }
}
