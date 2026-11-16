import QtQuick 6.11
import qs.Commons as Commons

// The card's type scale: three styles and nothing else.
//   heading  heading size, bold: a page's title line, a track title
//   body     body size: row labels and values
//   caption  small size, muted: summaries, secondary lines, tile captions
// `muted` dims any style one step further (muted chats, disabled rows).
// One line by default, elided; set `wrap` for a wrapped note.
Text {
  id: t

  property string kind: "body"
  property bool muted: false
  property bool wrap: false

  textFormat: Text.PlainText
  color: Commons.Color.popups.text
  opacity: t.muted ? 0.45 : (t.kind === "caption" ? 0.65 : 1)
  font.family: Commons.Style.font.family
  font.pixelSize: t.kind === "heading" ? Commons.Style.font.heading
                : (t.kind === "caption" ? Commons.Style.font.bodySmall : Commons.Style.font.body)
  font.bold: t.kind === "heading"
  elide: t.wrap ? Text.ElideNone : Text.ElideRight
  wrapMode: t.wrap ? Text.WordWrap : Text.NoWrap
  maximumLineCount: t.wrap ? 3 : 1
}
