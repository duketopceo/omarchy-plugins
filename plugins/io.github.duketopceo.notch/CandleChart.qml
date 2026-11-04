import QtQuick
import qs.Commons as Commons
import "Stocks.js" as Stocks

// The large chart: line (gradient area) or candles, thin gridlines, price
// axis on the right, time labels along the bottom, and a hover crosshair
// with a price/time tooltip. The Canvas repaints only when the data, style,
// size or tone change; the crosshair and tooltip are plain items, so hover
// never repaints it.
Item {
  id: chart

  property var points: []                 // [{t,o,h,l,c,v}] from Stocks.parseSeries
  property string range: "1M"
  property string style: "line"           // "line" | "candle"
  property color tone: "#8b8f98"
  property color textColor: Commons.Color.foreground
  property color dimColor: Commons.Color.muted
  property string family: Commons.Style.font.family
  property real prev: NaN                 // previous close (dashed baseline on 1D)

  readonly property bool candles: style === "candle"
  readonly property int axisWidth: 40
  readonly property int axisHeight: 12
  readonly property var shown: candles ? Stocks.aggregate(points || [], Math.max(8, Math.floor((width - axisWidth) / 4.5))) : (points || [])
  readonly property var span: Stocks.valueRange(shown, candles)
  readonly property var nice: Stocks.niceTicks(span.min, span.max, Math.max(2, Math.round(height / 28)))
  readonly property var sc: Stocks.scalePoints(shown, { w: width, h: height, left: 5, right: axisWidth + 3, top: 4, bottom: axisHeight }, nice.min, nice.max)
  property int hoverIndex: -1
  readonly property var hoverPoint: hoverIndex >= 0 && hoverIndex < shown.length ? shown[hoverIndex] : null

  function repaint() { canvas.requestPaint() }
  onShownChanged: repaint()
  onToneChanged: repaint()
  onWidthChanged: repaint()
  onHeightChanged: repaint()
  onStyleChanged: repaint()

  Canvas {
    id: canvas
    anchors.fill: parent
    onPaint: {
      var ctx = getContext("2d")
      ctx.reset()
      var s = chart.shown
      if (!s || s.length < 1 || width < 20 || height < 20) return
      var sc = chart.sc, plot = sc.plot
      // gridlines
      ctx.lineWidth = 1
      ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.06)
      ctx.beginPath()
      var ticks = chart.nice.ticks
      for (var i = 0; i < ticks.length; i++) {
        var gy = Math.round(sc.y(ticks[i])) + 0.5
        ctx.moveTo(plot.left, gy)
        ctx.lineTo(plot.left + plot.width, gy)
      }
      ctx.stroke()
      // previous close, dashed
      if (chart.range === "1D" && isFinite(chart.prev) && chart.prev >= chart.nice.min && chart.prev <= chart.nice.max) {
        var py = Math.round(sc.y(chart.prev)) + 0.5
        ctx.setLineDash([3, 3])
        ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.16)
        ctx.beginPath()
        ctx.moveTo(plot.left, py)
        ctx.lineTo(plot.left + plot.width, py)
        ctx.stroke()
        ctx.setLineDash([])
      }
      var tone = chart.tone
      if (chart.candles) {
        var step = s.length > 1 ? plot.width / (s.length - 1) : plot.width
        var bw = Math.max(1.5, Math.min(7, step * 0.68))
        for (var k = 0; k < s.length; k++) {
          var p = s[k], x = sc.x(k)
          var up = p.c >= p.o
          var col = up ? Stocks.COLORS.up : Stocks.COLORS.down
          ctx.strokeStyle = col
          ctx.fillStyle = col
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.moveTo(Math.round(x) + 0.5, sc.y(p.h))
          ctx.lineTo(Math.round(x) + 0.5, sc.y(p.l))
          ctx.stroke()
          var top = sc.y(Math.max(p.o, p.c)), bh = Math.max(1, Math.abs(sc.y(p.o) - sc.y(p.c)))
          ctx.fillRect(x - bw / 2, top, bw, bh)
        }
      } else {
        var grad = ctx.createLinearGradient(0, plot.top, 0, plot.top + plot.height)
        grad.addColorStop(0, Qt.rgba(tone.r, tone.g, tone.b, 0.30))
        grad.addColorStop(1, Qt.rgba(tone.r, tone.g, tone.b, 0.0))
        ctx.beginPath()
        ctx.moveTo(sc.xs[0], plot.top + plot.height)
        for (var a = 0; a < sc.xs.length; a++) ctx.lineTo(sc.xs[a], sc.ys[a])
        ctx.lineTo(sc.xs[sc.xs.length - 1], plot.top + plot.height)
        ctx.closePath()
        ctx.fillStyle = grad
        ctx.fill()
        ctx.beginPath()
        ctx.moveTo(sc.xs[0], sc.ys[0])
        for (var b = 1; b < sc.xs.length; b++) ctx.lineTo(sc.xs[b], sc.ys[b])
        ctx.strokeStyle = tone
        ctx.lineWidth = 1.6
        ctx.lineJoin = "round"
        ctx.stroke()
      }
    }
  }

  // price axis
  Repeater {
    model: chart.nice.ticks
    delegate: Text {
      required property var modelData
      textFormat: Text.PlainText
      x: chart.width - chart.axisWidth + 5
      y: chart.sc.y(modelData) - height / 2
      visible: y >= 0 && y + height <= chart.height - chart.axisHeight + 4
      text: Stocks.formatPrice(modelData)
      color: chart.dimColor
      font.family: chart.family
      font.pixelSize: 8
      font.features: ({ "tnum": 1 })
    }
  }

  // time axis
  Repeater {
    model: Stocks.axisIndices(chart.shown.length, 4)
    delegate: Text {
      required property var modelData
      required property int index
      textFormat: Text.PlainText
      readonly property real cx: chart.sc.x(modelData)
      x: Math.max(0, Math.min(chart.width - chart.axisWidth - width, cx - width / 2))
      y: chart.height - height
      text: chart.shown.length ? Stocks.formatTime(chart.shown[modelData].t, chart.range, true) : ""
      color: chart.dimColor
      font.family: chart.family
      font.pixelSize: 8
      font.features: ({ "tnum": 1 })
    }
  }

  // crosshair
  Rectangle {
    visible: chart.hoverPoint !== null
    x: chart.hoverIndex >= 0 ? Math.round(chart.sc.x(chart.hoverIndex)) : 0
    y: chart.sc.plot.top
    width: 1
    height: chart.sc.plot.height
    color: Qt.rgba(1, 1, 1, 0.28)
  }
  Rectangle {
    visible: chart.hoverPoint !== null
    width: 7; height: 7; radius: 4
    x: chart.hoverIndex >= 0 ? chart.sc.x(chart.hoverIndex) - 3.5 : 0
    y: chart.hoverPoint ? chart.sc.y(chart.hoverPoint.c) - 3.5 : 0
    color: chart.tone
    border.width: 1.5
    border.color: "black"
  }
  // price tag on the axis
  Rectangle {
    visible: chart.hoverPoint !== null
    x: chart.width - chart.axisWidth + 1
    y: chart.hoverPoint ? Math.max(0, Math.min(chart.height - chart.axisHeight - height, chart.sc.y(chart.hoverPoint.c) - height / 2)) : 0
    width: chart.axisWidth - 1
    height: 12
    radius: 3
    color: Qt.rgba(1, 1, 1, 0.9)
    Text {
      anchors.centerIn: parent
      textFormat: Text.PlainText
      text: chart.hoverPoint ? Stocks.formatPrice(chart.hoverPoint.c) : ""
      color: "black"
      font.family: chart.family
      font.pixelSize: 8
      font.weight: Font.DemiBold
      font.features: ({ "tnum": 1 })
    }
  }
  // tooltip
  Rectangle {
    id: tip
    visible: chart.hoverPoint !== null
    readonly property real anchorX: chart.hoverIndex >= 0 ? chart.sc.x(chart.hoverIndex) : 0
    x: Math.max(0, Math.min(chart.width - chart.axisWidth - width, anchorX + 8 + width > chart.width - chart.axisWidth ? anchorX - width - 8 : anchorX + 8))
    y: chart.sc.plot.top + 2
    width: tipCol.implicitWidth + 12
    height: tipCol.implicitHeight + 8
    radius: 5
    color: Qt.rgba(0.07, 0.07, 0.08, 0.94)
    border.width: 1
    border.color: Qt.rgba(1, 1, 1, 0.12)
    Column {
      id: tipCol
      anchors.centerIn: parent
      spacing: 1
      Text {
        textFormat: Text.PlainText
        text: chart.hoverPoint ? Stocks.formatTime(chart.hoverPoint.t, chart.range, false) : ""
        color: chart.dimColor
        font.family: chart.family
        font.pixelSize: 8
        font.features: ({ "tnum": 1 })
      }
      Text {
        textFormat: Text.PlainText
        text: !chart.hoverPoint ? "" : (chart.candles
          ? "O " + Stocks.formatPrice(chart.hoverPoint.o) + "  H " + Stocks.formatPrice(chart.hoverPoint.h)
            + "  L " + Stocks.formatPrice(chart.hoverPoint.l) + "  C " + Stocks.formatPrice(chart.hoverPoint.c)
          : Stocks.formatPrice(chart.hoverPoint.c))
        color: chart.textColor
        font.family: chart.family
        font.pixelSize: 9
        font.weight: Font.DemiBold
        font.features: ({ "tnum": 1 })
      }
      Text {
        textFormat: Text.PlainText
        visible: chart.hoverPoint !== null && chart.hoverPoint.v > 0
        text: chart.hoverPoint ? "Vol " + Stocks.formatVolume(chart.hoverPoint.v) : ""
        color: chart.dimColor
        font.family: chart.family
        font.pixelSize: 8
        font.features: ({ "tnum": 1 })
      }
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.NoButton
    onPositionChanged: function (m) { chart.hoverIndex = Stocks.nearest(chart.sc.xs, m.x) }
    onExited: chart.hoverIndex = -1
  }
}
