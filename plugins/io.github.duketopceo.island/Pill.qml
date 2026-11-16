import QtQuick 6.11
import qs.Commons as Commons

// The compact pill's content: the time in the left ear; in the right ear the
// top live activity (glyph plus its short ear text), or the short date when
// nothing is live. A second live activity shows only as a 16 px icon at the
// right ear's outer edge, and then the top drops its glyph (KTD10). Every
// label is single-line, elides, and never grows past the ear cap. The camera
// gap in the middle stays empty.
Item {
  id: pill

  property date now: new Date()
  property int earWidth: 56
  property int cameraWidth: 160
  property color textColor: Commons.Color.popups.text
  // From Activity.layout(): the top and second live activities, or null.
  property var topActivity: null
  property var secondActivity: null

  readonly property int pad: Commons.Style.spacing.lg
  readonly property int textWidth: Math.max(0, pill.earWidth - pill.pad)
  readonly property int iconWidth: 16
  readonly property string earText: pill.topActivity
    ? (pill.secondActivity ? pill.topActivity.text : pill.topActivity.glyph + " " + pill.topActivity.text)
    : Qt.formatDate(pill.now, "MMM d")

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
    id: secondIcon
    visible: pill.secondActivity !== null
    textFormat: Text.PlainText
    text: pill.secondActivity ? pill.secondActivity.glyph : ""
    color: pill.textColor
    opacity: 0.8
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    width: pill.secondActivity ? pill.iconWidth : 0
    horizontalAlignment: Text.AlignRight
    anchors.right: parent.right
    anchors.rightMargin: pill.pad
    anchors.verticalCenter: parent.verticalCenter
  }

  Text {
    id: earLabel
    textFormat: Text.PlainText
    text: pill.earText
    color: pill.textColor
    opacity: pill.topActivity ? 1 : 0.8
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    maximumLineCount: 1
    elide: Text.ElideRight
    width: Math.max(0, pill.textWidth - secondIcon.width)
    horizontalAlignment: Text.AlignRight
    anchors.right: secondIcon.left
    anchors.verticalCenter: parent.verticalCenter
  }
}
