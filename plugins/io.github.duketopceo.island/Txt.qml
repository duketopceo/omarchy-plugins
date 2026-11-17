import QtQuick 6.11
import qs.Commons as Commons

// The card's type scale: four styles and nothing else.
//   display  display size, bold: one big number per tile (a ring's percentage)
//   heading  heading size, bold: a page's title line, a track title
//   body     body size: names and values
//   caption  small size, muted: summaries, secondary lines, tile captions
// `muted` dims any style one step further (muted chats, disabled rows).
// `numeric` turns on tabular figures so a changing number does not jiggle.
// One line by default, elided; set `wrap` for a wrapped note. The typeface
// comes from Face.qml (Fonts.js), never from here.
Face {
  id: t

  property string kind: "body"
  property bool muted: false
  property bool wrap: false
  property bool numeric: false

  textFormat: Text.PlainText
  color: Commons.Color.popups.text
  opacity: t.muted ? 0.45 : (t.kind === "caption" ? 0.65 : 1)
  font.pixelSize: t.kind === "display" ? Commons.Style.font.display
                : (t.kind === "heading" ? Commons.Style.font.heading
                : (t.kind === "caption" ? Commons.Style.font.bodySmall : Commons.Style.font.body))
  font.bold: t.kind === "heading" || t.kind === "display"
  font.features: t.numeric ? { "tnum": 1 } : ({})
  elide: t.wrap ? Text.ElideNone : Text.ElideRight
  wrapMode: t.wrap ? Text.WordWrap : Text.NoWrap
  maximumLineCount: t.wrap ? 3 : 1
}
