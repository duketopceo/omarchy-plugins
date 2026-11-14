import QtQuick
import qs.Commons as Commons

// 60-second sparkline on a fixed scale. `values` is oldest first; null
// entries are gaps. Shows `label` (top left) and `readout` (top right) over
// the line, or `emptyText` when there is nothing to draw.
Rectangle {
  id: spark

  property var values: []
  property real minValue: 0
  property real maxValue: 100
  property color tone: Tk.sky
  property string label: ""
  property string readout: ""
  property string emptyText: "n/a"
  property color textColor: Tk.text
  property color dimColor: Tk.dim
  property string family: Commons.Style.font.family
  readonly property bool hasData: {
    var v = values || []
    for (var i = 0; i < v.length; i++) if (v[i] !== null && v[i] !== undefined) return true
    return false
  }

  radius: Tk.r(6)
  color: Tk.tint(0.05)
  clip: true

  onValuesChanged: canvas.requestPaint()
  onToneChanged: canvas.requestPaint()
  onWidthChanged: canvas.requestPaint()
  onHeightChanged: canvas.requestPaint()
  onMinValueChanged: canvas.requestPaint()
  onMaxValueChanged: canvas.requestPaint()

  Canvas {
    id: canvas
    anchors.fill: parent
    onPaint: {
      var ctx = getContext("2d")
      ctx.reset()
      var vals = spark.values || []
      if (!spark.hasData || width < 4) return
      var n = 30
      var span = Math.max(1e-6, spark.maxValue - spark.minValue)
      var top = 14, bottom = 3
      var step = width / (n - 1)
      var x0 = width - (vals.length - 1) * step
      function X(i) { return x0 + i * step }
      function Y(v) { return top + (height - top - bottom) * (1 - Math.max(0, Math.min(1, (v - spark.minValue) / span))) }
      var tone = spark.tone
      var segStart = -1
      function flush(end) {
        if (segStart < 0) return
        var grad = ctx.createLinearGradient(0, top, 0, height)
        grad.addColorStop(0, Tk.alpha(tone, 0.28))
        grad.addColorStop(1, Tk.alpha(tone, 0))
        ctx.beginPath()
        ctx.moveTo(X(segStart), height)
        for (var a = segStart; a <= end; a++) ctx.lineTo(X(a), Y(vals[a]))
        ctx.lineTo(X(end), height)
        ctx.closePath()
        ctx.fillStyle = Tk.pxl ? Tk.card : grad
        ctx.fill()
        ctx.beginPath()
        ctx.moveTo(X(segStart), Y(vals[segStart]))
        for (var b = segStart + 1; b <= end; b++) ctx.lineTo(X(b), Y(vals[b]))
        ctx.strokeStyle = tone
        ctx.lineWidth = 1.3
        ctx.lineJoin = "round"
        ctx.stroke()
        segStart = -1
      }
      for (var i = 0; i < vals.length; i++) {
        if (vals[i] === null || vals[i] === undefined) flush(i - 1)
        else if (segStart < 0) segStart = i
      }
      flush(vals.length - 1)
    }
  }

  Text {
    textFormat: Text.PlainText
    anchors.left: parent.left
    anchors.leftMargin: 5
    anchors.top: parent.top
    anchors.topMargin: 2
    text: spark.label
    color: spark.dimColor
    font.family: spark.family
    font.pixelSize: Tk.fs.caption
  }
  Text {
    textFormat: Text.PlainText
    anchors.right: parent.right
    anchors.rightMargin: 5
    anchors.top: parent.top
    anchors.topMargin: 2
    text: spark.hasData ? spark.readout : spark.emptyText
    color: spark.hasData ? spark.textColor : spark.dimColor
    font.family: spark.family
    font.pixelSize: Tk.fs.caption
    font.weight: Font.DemiBold
  }
}
