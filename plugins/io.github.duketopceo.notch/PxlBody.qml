import QtQuick

// Pixel-stepped island silhouette: square top (attached to the screen), the
// two bottom corners chamfered in 2px steps, with a 2px edge line. Drawn as
// stacked plain rectangles so everything lands on whole pixels.
Item {
  id: body
  property color fill: "black"
  property color edge: "gray"
  property int bw: 2
  Repeater {
    model: 6
    Rectangle {
      required property int index
      readonly property bool inner: index >= 3
      readonly property int k: index % 3
      readonly property int inset: k * 2 + (inner ? body.bw : 0)
      readonly property int cut: (2 - k) * 2 + (inner ? body.bw : 0)
      x: inset
      y: 0
      width: Math.max(0, Math.round(body.width) - 2 * inset)
      height: Math.max(0, Math.round(body.height) - cut)
      color: inner ? body.fill : body.edge
    }
  }
}
