import QtQuick 6.11
import qs.Commons as Commons

// The split presentation's minimal bubble (R3, KTD6): the second live
// activity's glyph in a circle beside the pill, flush with the top edge like
// the pill. Pure black on a notch screen, theme colors elsewhere. A click
// asks the window to open the card with this activity on top; hovering it
// opens the card through the normal hover rules.
Item {
  id: bubble

  property var activity: null
  property bool notch: false
  property color textColor: Commons.Color.popups.text
  signal clicked()

  Rectangle {
    // Taller than the bubble and clipped by nothing: the top half sits above
    // the screen edge, so only the lower half's round shows.
    y: -bubble.height / 2
    width: bubble.width
    height: bubble.height * 1.5
    radius: bubble.width / 2
    color: bubble.notch ? Qt.rgba(0, 0, 0, 1) : Commons.Color.popups.background
    border.width: bubble.notch ? 0 : Commons.Style.normalBorderWidth
    border.color: Commons.Color.popups.border
  }

  // The glyph brightens under the pointer and the bubble dips to 0.96 while
  // pressed; the pointing hand marks it as clickable. (The card opens by the
  // normal hover rules, so there is no hint here: nothing to draw it in.)
  Text {
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: bubble.activity ? bubble.activity.glyph : ""
    color: bubble.textColor
    opacity: hover.hovered ? 1 : 0.8
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
  }

  scale: tap.pressed ? 0.96 : 1
  Behavior on scale { NumberAnimation { duration: Commons.Style.duration(70) } }

  HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
  TapHandler { id: tap; onTapped: bubble.clicked() }
}
