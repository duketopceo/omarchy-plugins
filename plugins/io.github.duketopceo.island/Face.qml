import QtQuick 6.11
import qs.Commons as Commons

// Text in the Island's UI face (Fonts.js). It finds the face by walking up to
// the first ancestor that publishes `uiFont` (the window's stage), so the
// typeface is decided in exactly one place and flips with the `sansFont`
// setting. `icon: true` keeps the shell's face for glyph-only text (the Nerd
// Font symbols live there; a glyph inside a label falls back through
// fontconfig). With no such ancestor it uses the shell's face.
Text {
  id: t

  property bool icon: false
  property var faceHost: null

  readonly property string face: t.icon || t.faceHost === null ? Commons.Style.font.family : t.faceHost.uiFont

  font.family: t.face

  Component.onCompleted: {
    var p = t.parent
    while (p) {
      if (p.uiFont !== undefined) { t.faceHost = p; break }
      p = p.parent
    }
  }
}
