import QtQuick
import "Stocks.js" as Stocks

// Tiny line chart with a soft gradient underneath. Repaints only when the
// values, color or size change.
Canvas {
  id: spark

  property var values: []                 // closes, oldest first
  property color tone: Tk.gray
  property real lineWidth: 1.4

  onValuesChanged: requestPaint()
  onToneChanged: requestPaint()
  onWidthChanged: requestPaint()
  onHeightChanged: requestPaint()

  onPaint: {
    var ctx = getContext("2d")
    ctx.reset()
    var vals = values || []
    if (vals.length < 2 || width < 4 || height < 4) return
    var pts = []
    for (var i = 0; i < vals.length; i++) pts.push({ c: vals[i] })
    var r = Stocks.valueRange(pts, false)
    var sc = Stocks.scalePoints(pts, { w: width, h: height, left: 1, right: 1, top: 2, bottom: 2 }, r.min, r.max)
    var grad = ctx.createLinearGradient(0, 0, 0, height)
    grad.addColorStop(0, Tk.alpha(tone, 0.30))
    grad.addColorStop(1, Tk.alpha(tone, 0.0))
    ctx.beginPath()
    ctx.moveTo(sc.xs[0], height)
    for (var a = 0; a < sc.xs.length; a++) ctx.lineTo(sc.xs[a], sc.ys[a])
    ctx.lineTo(sc.xs[sc.xs.length - 1], height)
    ctx.closePath()
    ctx.fillStyle = Tk.pxl ? Tk.card : grad
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(sc.xs[0], sc.ys[0])
    for (var b = 1; b < sc.xs.length; b++) ctx.lineTo(sc.xs[b], sc.ys[b])
    ctx.strokeStyle = tone
    ctx.lineWidth = lineWidth
    ctx.lineJoin = "round"
    ctx.stroke()
  }
}
