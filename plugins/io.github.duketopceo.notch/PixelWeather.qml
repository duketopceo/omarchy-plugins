import QtQuick
import "PixelArt.js" as PixelArt

// A tiny animated pixel-art weather icon (14x14 logical px). Frames come from
// PixelArt.js; the Canvas renders at the screen's native resolution (the Canvas is DPR-aware) with hard pixel edges.
Item {
  id: icon

  property string kind: "cloudy"
  property bool active: true       // animate only while visible
  property int frameMs: 650
  property int px: 1               // screen px per sprite pixel (integer keeps edges hard)
  readonly property int cells: PixelArt.SPRITE_SIZE
  property int frame: 0

  implicitWidth: cells * px
  implicitHeight: cells * px
  width: implicitWidth
  height: implicitHeight

  Timer {
    interval: icon.frameMs
    running: icon.active && icon.visible
    repeat: true
    onTriggered: icon.frame = PixelArt.spriteFrame(icon.kind, (icon.frame + 1) * icon.frameMs, icon.frameMs)
  }

  onPxChanged: canvas.requestPaint()
  onKindChanged: { frame = 0; canvas.requestPaint() }
  onFrameChanged: canvas.requestPaint()

  Canvas {
    id: canvas
    anchors.fill: parent
    smooth: false
    onPaint: {
      var ctx = getContext("2d")
      ctx.clearRect(0, 0, width, height)
      var frames = PixelArt.weatherSprite(icon.kind)
      var rows = frames[icon.frame % frames.length]
      for (var y = 0; y < rows.length; y++) {
        for (var x = 0; x < rows[y].length; x++) {
          var c = PixelArt.SPRITE_COLORS[rows[y].charAt(x)]
          if (!c) continue
          ctx.fillStyle = c
          ctx.fillRect(x * icon.px, y * icon.px, icon.px, icon.px)
        }
      }
    }
  }
}
