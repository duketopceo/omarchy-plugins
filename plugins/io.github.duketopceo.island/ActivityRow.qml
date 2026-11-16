import QtQuick 6.11
import qs.Commons as Commons
import "Glyphs.js" as Glyphs

// One live activity on Home: glyph, card text, and the activity's controls
// (Glyphs.rowControls: Stop, play/pause, the timer's pause/resume, +1 min and
// cancel, calendar Join), if it has any.
Item {
  id: row

  property var activity: null
  signal act(string id, string action)

  readonly property string activityId: row.activity ? String(row.activity.id) : ""
  // Reassigned only when the set changes: a running timer redraws each
  // second, and a new model would rebuild its buttons mid-click.
  property var controls: []
  readonly property string controlKey: Glyphs.rowControls(row.activity).join(",")
  function syncControls() { row.controls = row.controlKey === "" ? [] : row.controlKey.split(",") }
  onControlKeyChanged: row.syncControls()
  Component.onCompleted: row.syncControls()

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
    anchors.right: buttons.left
    anchors.rightMargin: Commons.Style.spacing.lg
    anchors.verticalCenter: parent.verticalCenter
  }

  Row {
    id: buttons
    spacing: Commons.Style.spacing.md
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter

    Repeater {
      model: row.controls

      ActivityButton {
        required property string modelData
        label: Glyphs.controlLabel(modelData, row.activity)
        onClicked: row.act(row.activityId, modelData)
      }
    }
  }
}
