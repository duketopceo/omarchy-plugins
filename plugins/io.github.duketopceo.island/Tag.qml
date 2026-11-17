import QtQuick 6.11
import qs.Commons as Commons
import "Glyphs.js" as Glyphs

// A small count pill: a colored dot (or a check) and a short caption, on a
// soft plate. Display only. Agents' header uses it for "1 working".
Rectangle {
  id: tag

  property string text: ""
  property color tone: Commons.Color.accent
  // "dot" | "check"
  property string mark: "dot"
  property bool dim: false

  readonly property int dotSize: Commons.Style.spacing.lg

  implicitWidth: row.implicitWidth + Commons.Style.spacing.xl * 2
  implicitHeight: Commons.Style.space(22)
  height: implicitHeight
  radius: height / 2
  color: Qt.alpha(Commons.Color.popups.text, 0.06)
  opacity: tag.dim ? 0.6 : 1

  Row {
    id: row
    anchors.centerIn: parent
    spacing: Commons.Style.spacing.md

    Rectangle {
      visible: tag.mark === "dot"
      width: tag.dotSize; height: width; radius: width / 2
      anchors.verticalCenter: parent.verticalCenter
      color: tag.tone
    }
    Txt {
      visible: tag.mark === "check"
      icon: true
      kind: "caption"
      opacity: 1
      color: tag.tone
      text: Glyphs.GLYPHS.check
      anchors.verticalCenter: parent.verticalCenter
    }
    Txt {
      kind: "caption"
      opacity: 1
      text: tag.text
      anchors.verticalCenter: parent.verticalCenter
    }
  }
}
