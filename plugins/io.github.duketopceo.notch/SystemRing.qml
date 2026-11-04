import QtQuick
import qs.Commons as Commons

// Compact progress ring: `value` 0..1 (null/negative = no reading, shows the
// bare track), centered `text`.
Item {
  id: ring

  property real value: -1
  property color tone: "#6fa8ff"
  property color track: Qt.rgba(1, 1, 1, 0.10)
  property string text: ""
  property color textColor: Commons.Color.foreground
  property string family: Commons.Style.font.family
  property real thickness: 5

  onValueChanged: canvas.requestPaint()
  onToneChanged: canvas.requestPaint()
  onWidthChanged: canvas.requestPaint()

  Canvas {
    id: canvas
    anchors.fill: parent
    onPaint: {
      var ctx = getContext("2d")
      ctx.reset()
      var r = Math.min(width, height) / 2 - ring.thickness / 2
      var cx = width / 2, cy = height / 2
      ctx.lineWidth = ring.thickness
      ctx.lineCap = "round"
      ctx.strokeStyle = ring.track
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.stroke()
      if (ring.value > 0) {
        var v = Math.min(1, ring.value)
        ctx.strokeStyle = ring.tone
        ctx.beginPath()
        ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * v)
        ctx.stroke()
      }
    }
  }

  Text {
    textFormat: Text.PlainText
    anchors.centerIn: parent
    text: ring.text
    color: ring.textColor
    font.family: ring.family
    font.pixelSize: 12
    font.weight: Font.DemiBold
  }
}
