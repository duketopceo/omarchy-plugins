import QtQuick 6.11
import qs.Commons as Commons

// Now Playing glyph (R12): bars that bounce while media plays and stand still
// at their resting heights when paused or when the owner asked for reduced
// motion (Commons.Style.duration returns 0 then). `levels` sets the bar count
// and the resting heights (0..1); the width is spread across the bars.
Item {
  id: eq

  property bool playing: false
  property color color: Commons.Color.popups.text
  property var levels: [0.55, 1.0, 0.75]

  readonly property bool moving: eq.playing && Commons.Style.duration(300) > 0
  readonly property int count: Math.max(1, eq.levels.length)
  // Bars and equal gaps between them: count bars + (count - 1) gaps.
  readonly property int barWidth: Math.max(2, Math.floor(eq.width / (eq.count * 2 - 1)))

  implicitWidth: 14
  implicitHeight: 12

  Repeater {
    model: eq.levels

    Rectangle {
      id: bar
      required property real modelData
      required property int index
      // Resting heights differ so a paused glyph still reads as an equalizer.
      property real level: bar.modelData
      x: Math.round(bar.index * (eq.width - eq.barWidth) / Math.max(1, eq.count - 1))
      width: eq.barWidth
      height: Math.max(2, eq.height * bar.level)
      anchors.bottom: parent.bottom
      radius: width / 2
      color: eq.color

      SequentialAnimation on level {
        running: eq.moving
        loops: Animation.Infinite
        alwaysRunToEnd: false
        NumberAnimation { to: 0.25; duration: 260 + bar.index * 70; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1.0; duration: 300 + bar.index * 50; easing.type: Easing.InOutSine }
        NumberAnimation { to: bar.modelData; duration: 220; easing.type: Easing.InOutSine }
      }
    }
  }

  onMovingChanged: if (!eq.moving) for (var i = 0; i < children.length; i++) if (children[i].modelData !== undefined) children[i].level = children[i].modelData
}
