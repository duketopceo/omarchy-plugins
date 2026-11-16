import QtQuick 6.11
import qs.Commons as Commons
import "Tint.js" as Tint

// One activity control: a glyph or short label in a bordered chip. A control
// whose capability is off draws dimmed and ignores clicks. Clicking never
// raises the card's keyboard focus (KTD4); the parent only receives `clicked`.
Rectangle {
  id: btn

  property string label: ""
  property bool available: true
  property bool emphasized: false
  property color accent: Commons.Color.accent
  signal clicked()

  // The emphasized fill is the menu's selected background laid over the popup
  // background. An art-derived accent that does not reach 3:1 on it falls
  // back to the menu's selected-text color.
  readonly property color fill: Qt.tint(Commons.Color.popups.background, Commons.Color.menu.selectedBackground)
  readonly property color ink: Tint.contrast({ r: btn.accent.r, g: btn.accent.g, b: btn.accent.b },
                                             { r: btn.fill.r, g: btn.fill.g, b: btn.fill.b }) >= 3
    ? btn.accent : Commons.Color.menu.selectedText

  implicitWidth: Math.max(Commons.Style.spacing.controlHeight, labelText.implicitWidth + Commons.Style.spacing.huge)
  implicitHeight: Commons.Style.spacing.controlHeight
  radius: Commons.Style.cornerRadius
  color: btn.emphasized ? Commons.Color.menu.selectedBackground : "transparent"
  border.width: Commons.Style.normalBorderWidth
  border.color: btn.emphasized ? btn.ink : Commons.Color.menu.border
  opacity: btn.available ? 1 : 0.35

  Text {
    id: labelText
    textFormat: Text.PlainText
    text: btn.label
    color: btn.emphasized ? btn.ink : Commons.Color.popups.text
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
