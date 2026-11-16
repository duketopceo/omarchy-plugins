import QtQuick 6.11
import qs.Commons as Commons
import "Glyphs.js" as Glyphs

// One further activity under the top block: glyph, card text, and the
// activity's primary control (Stop, play/pause, pause/resume), if it has one.
Item {
  id: row

  property var activity: null
  signal act(string id, string action)

  readonly property string activityId: row.activity ? String(row.activity.id) : ""
  readonly property string control: Glyphs.primaryControl(row.activity)

  implicitHeight: Commons.Style.spacing.controlHeight

  Text {
    id: glyphText
    textFormat: Text.PlainText
    text: row.activity ? row.activity.glyph : ""
    color: Commons.Color.popups.text
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.heading
    width: Commons.Style.spacing.controlHeight
    horizontalAlignment: Text.AlignHCenter
    anchors.verticalCenter: parent.verticalCenter
  }

  Text {
    textFormat: Text.PlainText
    text: row.activity ? row.activity.card : ""
    color: Commons.Color.popups.text
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.body
    elide: Text.ElideRight
    maximumLineCount: 1
    anchors.left: glyphText.right
    anchors.leftMargin: Commons.Style.spacing.lg
    anchors.right: button.left
    anchors.rightMargin: Commons.Style.spacing.lg
    anchors.verticalCenter: parent.verticalCenter
  }

  ActivityButton {
    id: button
    visible: row.control !== ""
    width: row.control !== "" ? implicitWidth : 0
    label: Glyphs.controlLabel(row.control, row.activity)
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    onClicked: row.act(row.activityId, row.control)
  }
}
