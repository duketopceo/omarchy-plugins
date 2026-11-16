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

  Text {
    anchors.centerIn: parent
    textFormat: Text.PlainText
    text: bubble.activity ? bubble.activity.glyph : ""
    color: bubble.textColor
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
  }

  TapHandler { onTapped: bubble.clicked() }
}
