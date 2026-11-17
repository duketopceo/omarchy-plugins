import QtQuick 6.11
import qs.Commons as Commons

// A circular gauge: a faint track and an arc from twelve o'clock for `level`
// (0..1). The caller puts the big number in the middle (default content).
// The arc eases to a new level (Commons.Style.duration, so reduced motion
// snaps) and never animates the item's size.
Item {
  id: ring

  property real level: 0
  property color tone: Commons.Color.accent
  property real lineWidth: Commons.Style.space(7)
  default property alias content: center.data

  readonly property color track: Qt.alpha(Commons.Color.popups.text, 0.12)
  property real shown: Math.max(0, Math.min(1, ring.level))

  Behavior on shown { NumberAnimation { duration: Commons.Style.duration(240); easing.type: Easing.OutCubic } }

  onShownChanged: canvas.requestPaint()
  onToneChanged: canvas.requestPaint()
  onTrackChanged: canvas.requestPaint()
  onWidthChanged: canvas.requestPaint()
  onHeightChanged: canvas.requestPaint()

  Canvas {
    id: canvas
    anchors.fill: parent
    antialiasing: true
    onPaint: {
      var ctx = getContext("2d")
      ctx.reset()
      var w = ring.lineWidth
      var r = (Math.min(width, height) - w) / 2
      var cx = width / 2
      var cy = height / 2
      ctx.lineWidth = w
      ctx.lineCap = "round"
      ctx.strokeStyle = ring.track
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.stroke()
      if (ring.shown > 0.004) {
        var start = -Math.PI / 2
        ctx.strokeStyle = ring.tone
        ctx.beginPath()
        ctx.arc(cx, cy, r, start, start + Math.PI * 2 * ring.shown)
        ctx.stroke()
      }
    }
  }

  Item {
    id: center
    anchors.fill: parent
  }
}
