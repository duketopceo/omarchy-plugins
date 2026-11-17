import QtQuick 6.11
import qs.Commons as Commons

// A simple list page (Shots, Messages, Dayflow): a caption summary with an
// optional action on the right, then label/value rows. A row with a `name`
// (Shots) or a `chat` (Messages) is a hover button that activates it; other
// rows only display. A `muted` row is drawn dimmed. With no rows the page
// shows one centered empty line.
Item {
  id: page

  property string summary: ""
  property string actionLabel: ""
  property string actionHint: ""
  // Hover hint for a clickable row.
  property string rowHint: ""
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

      Txt {
        anchors.left: parent.left
        anchors.right: actionButton.visible ? actionButton.left : parent.right
        anchors.rightMargin: Commons.Style.spacing.lg
        anchors.verticalCenter: parent.verticalCenter
        kind: "caption"
        text: page.summary
      }
      ActivityButton {
        id: actionButton
        visible: page.actionLabel !== ""
        label: page.actionLabel
        hint: page.actionHint
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        onClicked: page.action()
      }
    }

    EmptyNote {
      visible: (page.rows || []).length === 0
      width: parent.width
      height: page.rowH + page.gap
      text: page.emptyText
    }

    Column {
      width: parent.width
      spacing: page.gap

      Repeater {
        model: (page.rows || []).slice(0, Math.max(0, page.maxRows))

        HoverButton {
          id: item
          required property var modelData
          readonly property bool clickable: (typeof item.modelData.name === "string" && item.modelData.name !== "")
            || (typeof item.modelData.chat === "string" && item.modelData.chat !== "")
          readonly property bool muted: item.modelData.muted === true
          passive: !item.clickable
          hint: item.clickable ? page.rowHint : ""
          width: parent.width
          height: page.rowH
          onClicked: page.activated(item.modelData)

          Txt {
            anchors.left: parent.left
            anchors.leftMargin: Commons.Style.spacing.md
            anchors.right: value.left
            anchors.rightMargin: Commons.Style.spacing.lg
            anchors.verticalCenter: parent.verticalCenter
            muted: item.muted
            text: item.modelData.label
          }
          Txt {
            id: value
            anchors.right: parent.right
            anchors.rightMargin: Commons.Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            kind: "caption"
            muted: item.muted
            font.features: { "tnum": 1 }
            text: item.modelData.value
          }
        }
      }
    }
  }
}
