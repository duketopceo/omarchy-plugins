import QtQuick 6.11
import qs.Commons as Commons

// One activity control: a glyph or short label in a bordered chip. A control
// whose capability is off draws dimmed and ignores clicks. Clicking never
// raises the card's keyboard focus (KTD4); the parent only receives `clicked`.
Rectangle {
  id: btn

  property string label: ""
  property bool available: true
  property bool emphasized: false
  signal clicked()

  implicitWidth: Math.max(Commons.Style.spacing.controlHeight, labelText.implicitWidth + Commons.Style.spacing.huge)
  implicitHeight: Commons.Style.spacing.controlHeight
  radius: Commons.Style.cornerRadius
  color: btn.emphasized ? Commons.Color.menu.selectedBackground : "transparent"
  border.width: Commons.Style.normalBorderWidth
  border.color: btn.emphasized ? Commons.Color.accent : Commons.Color.menu.border
  opacity: btn.available ? 1 : 0.35

  Text {
    id: labelText
    textFormat: Text.PlainText
    text: btn.label
    color: btn.emphasized ? Commons.Color.accent : Commons.Color.popups.text
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.body
    anchors.centerIn: parent
  }

  MouseArea {
    anchors.fill: parent
    enabled: btn.available
    onClicked: btn.clicked()
  }
}
