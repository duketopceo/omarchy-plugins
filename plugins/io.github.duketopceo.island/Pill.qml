import QtQuick 6.11
import qs.Commons as Commons

// The compact pill's content: the time in the left ear, the short date in the
// right ear. Both are single-line, elide, and never grow past the ear cap. The
// camera gap in the middle stays empty.
Item {
  id: pill

  property date now: new Date()
  property int earWidth: 56
  property int cameraWidth: 160
  property color textColor: Commons.Color.popups.text

  readonly property int pad: Commons.Style.spacing.lg
  readonly property int textWidth: Math.max(0, pill.earWidth - pill.pad)

  Text {
    id: timeText
    textFormat: Text.PlainText
    text: Qt.formatTime(pill.now, Qt.locale().timeFormat(Locale.ShortFormat))
    color: pill.textColor
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    maximumLineCount: 1
    elide: Text.ElideRight
    width: pill.textWidth
    horizontalAlignment: Text.AlignLeft
    anchors.left: parent.left
    anchors.leftMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }

  Text {
    id: dateText
    textFormat: Text.PlainText
    text: Qt.formatDate(pill.now, "MMM d")
    color: pill.textColor
    opacity: 0.8
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    maximumLineCount: 1
    elide: Text.ElideRight
    width: pill.textWidth
    horizontalAlignment: Text.AlignRight
    anchors.right: parent.right
    anchors.rightMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }
}
