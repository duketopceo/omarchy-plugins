import QtQuick

// Tiny animated equalizer: three bars bouncing out of phase while `playing`.
Row {
  id: eq
  property bool playing: false
  property color color: "white"
  spacing: 2
  height: 10
  Repeater {
    model: [0, 1, 2]
    Rectangle {
      id: bar
      required property int modelData
      width: 2
      radius: 1
      color: eq.color
      anchors.bottom: parent.bottom
      height: eq.playing ? 3 : 2
      SequentialAnimation on height {
        running: eq.playing
        loops: Animation.Infinite
        NumberAnimation { to: 10; duration: 320 + bar.modelData * 90; easing.type: Easing.InOutSine }
        NumberAnimation { to: 3; duration: 380 - bar.modelData * 60; easing.type: Easing.InOutSine }
      }
    }
  }
}
