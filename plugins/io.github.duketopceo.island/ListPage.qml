import QtQuick 6.11
import qs.Commons as Commons

// A simple list page (Shots, Messages, Dayflow): a summary line with an
// optional action on the right, then label/value rows. A row with a `name`
// is clickable (Shots opens the screenshot).
Item {
  id: page

  property string summary: ""
  property string actionLabel: ""
  property string emptyText: "Nothing here"
  property var rows: []
  property int maxRows: 0

  signal action()
  signal activated(var row)

  readonly property int maxList: 6
  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int gap: Commons.Style.spacing.sm

  function count() { return Math.min(page.maxList, (page.rows || []).length) }
  function heightFor(n) { return top.height + Commons.Style.spacing.lg + Math.max(1, n) * (page.rowH + page.gap) }

  Column {
    width: parent.width
    spacing: Commons.Style.spacing.lg

    Item {
      id: top
      width: parent.width
      height: page.rowH

      Text {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        textFormat: Text.PlainText
        text: page.summary
        color: Commons.Color.popups.text
        opacity: 0.75
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
      }
      ActivityButton {
        visible: page.actionLabel !== ""
        label: page.actionLabel
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        onClicked: page.action()
      }
    }

    Text {
      visible: (page.rows || []).length === 0
      textFormat: Text.PlainText
      text: page.emptyText
      color: Commons.Color.popups.text
      opacity: 0.7
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
    }

    Column {
      width: parent.width
      spacing: page.gap

      Repeater {
        model: (page.rows || []).slice(0, Math.max(0, page.maxRows))

        Rectangle {
          id: item
          required property var modelData
          readonly property bool clickable: typeof item.modelData.name === "string" && item.modelData.name !== ""
          width: parent.width
          height: page.rowH
          radius: Commons.Style.cornerRadius
          color: hover.containsMouse && item.clickable ? Commons.Color.menu.selectedBackground : "transparent"

          Text {
            anchors.left: parent.left
            anchors.leftMargin: Commons.Style.spacing.md
            anchors.right: value.left
            anchors.rightMargin: Commons.Style.spacing.lg
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: item.modelData.label
            color: Commons.Color.popups.text
            elide: Text.ElideRight
            maximumLineCount: 1
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
          }
          Text {
            id: value
            anchors.right: parent.right
            anchors.rightMargin: Commons.Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: item.modelData.value
            color: Commons.Color.popups.text
            opacity: 0.7
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
            font.features: { "tnum": 1 }
          }
          MouseArea {
            id: hover
            anchors.fill: parent
            hoverEnabled: true
            enabled: item.clickable
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: page.activated(item.modelData)
          }
        }
      }
    }
  }
}
