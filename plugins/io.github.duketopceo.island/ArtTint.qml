import QtQuick 6.11
import "Palette.js" as Palette

// Reads the track art's dominant colors. The art is drawn onto a 24 px canvas
// (Qt's loader fetches https art and decodes file: and data: art, held in
// memory only) and the pixels go to Palette.dominant(). Quickshell's
// ColorQuantizer could not do this: it reads local files only. The canvas is
// kept almost transparent and under the island's own background, so it never
// shows. `colors` is [{r, g, b}] in 0..1, empty while loading or on failure.
Canvas {
  id: tint

  property string source: ""
  property var colors: []

  // The source currently held by the canvas, so it can be released.
  property string held: ""
  readonly property int size: 24

  width: tint.size
  height: tint.size
  renderTarget: Canvas.Image
  renderStrategy: Canvas.Immediate
  opacity: 0.02

  onSourceChanged: {
    if (tint.held !== "") tint.unloadImage(tint.held)
    tint.held = ""
    tint.colors = []
    if (tint.source === "") return
    tint.held = tint.source
    tint.loadImage(tint.source)
  }

  onImageLoaded: tint.requestPaint()

  onPaint: {
    if (tint.held === "" || !tint.isImageLoaded(tint.held)) return
    var ctx = tint.getContext("2d")
    ctx.clearRect(0, 0, tint.size, tint.size)
    ctx.drawImage(tint.held, 0, 0, tint.size, tint.size)
    tint.colors = Palette.dominant(ctx.getImageData(0, 0, tint.size, tint.size).data)
  }

  Component.onDestruction: if (tint.held !== "") tint.unloadImage(tint.held)
}
