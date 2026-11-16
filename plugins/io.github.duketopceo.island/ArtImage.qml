import QtQuick 6.11
import Quickshell.Widgets
import qs.Commons as Commons
import "Glyphs.js" as Glyphs

// Rounded album art: the picture once it has loaded, the music glyph on a
// faint plate while it loads, when there is no art, or when loading fails.
// `source` is already filtered by Media.artUrl(). Every instance asks for the
// same decoded size, so the pill's thumbnail and the card's art share one
// cached image (and one download) in Qt's in-memory pixmap cache.
ClippingRectangle {
  id: art

  property string source: ""
  property color ink: Commons.Color.popups.text
  property int glyphSize: Commons.Style.font.body

  readonly property bool ready: image.status === Image.Ready

  color: Qt.alpha(art.ink, 0.12)

  Image {
    id: image
    anchors.fill: parent
    source: art.source
    asynchronous: true
    cache: true
    fillMode: Image.PreserveAspectCrop
    sourceSize.width: 192
    sourceSize.height: 192
    opacity: art.ready ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Commons.Style.duration(160) } }
  }

  Text {
    visible: !art.ready
    textFormat: Text.PlainText
    text: Glyphs.GLYPHS.music
    color: art.ink
    opacity: 0.8
    font.family: Commons.Style.font.family
    font.pixelSize: art.glyphSize
    anchors.centerIn: parent
  }
}
