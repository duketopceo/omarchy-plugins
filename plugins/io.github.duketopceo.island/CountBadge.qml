import QtQuick 6.11
import qs.Commons as Commons

// An unread badge: a small accent pill with a count, or a plain accent dot
// when `text` is empty. Display only; the parent places it in a corner.
Rectangle {
  id: badge

  property string text: ""
  // A muted badge is an outline in the text color, not a fill.
  property bool muted: false

  readonly property int dot: Commons.Style.spacing.xl
  readonly property int size: Commons.Style.space(18)

  implicitWidth: badge.text === "" ? badge.dot : Math.max(badge.size, label.implicitWidth + Commons.Style.spacing.lg * 2)
  implicitHeight: badge.text === "" ? badge.dot : badge.size
  width: implicitWidth
  height: implicitHeight
  radius: height / 2
  color: badge.muted ? "transparent" : Commons.Color.accent
  border.width: badge.muted ? Commons.Style.normalBorderWidth : 0
  border.color: Qt.alpha(Commons.Color.popups.text, 0.4)

  Txt {
    id: label
    visible: badge.text !== ""
    anchors.centerIn: parent
    width: implicitWidth
    kind: "caption"
    opacity: 1
    font.bold: true
    numeric: true
    color: badge.muted ? Qt.alpha(Commons.Color.popups.text, 0.7) : Commons.Color.popups.background
    text: badge.text
  }
}
