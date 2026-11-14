import QtQuick

// Progress/meter bar. Swift: rounded track + fill (as before). Pxl: chunky
// segmented blocks on whole pixels, no easing.
Item {
  id: bar
  property real value: 0          // 0..1
  property color fill: Tk.accent
  property color track: Tk.tint(0.1)
  property int segW: 6
  property int gap: 2
  property int swiftHeight: 6
  implicitHeight: Tk.pxl ? 8 : swiftHeight
  height: implicitHeight

  Rectangle {
    visible: !Tk.pxl
    anchors.fill: parent
    radius: Tk.r(height / 2)
    color: bar.track
    Rectangle {
      width: parent.width * Math.max(0, Math.min(1, bar.value))
      height: parent.height
      radius: Tk.r(height / 2)
      color: bar.fill
      Behavior on width { NumberAnimation { duration: Tk.ms(200); easing.type: Easing.OutQuad } }
    }
  }
  Row {
    visible: Tk.pxl
    spacing: bar.gap
    readonly property int n: Math.max(1, Math.floor((bar.width + bar.gap) / (bar.segW + bar.gap)))
    readonly property int lit: Math.round(Math.max(0, Math.min(1, bar.value)) * n)
    Repeater {
      model: parent.n
      Rectangle {
        required property int index
        width: bar.segW; height: bar.height
        color: index < parent.lit ? bar.fill : bar.track
      }
    }
  }
}
