import QtQuick 6.11
import qs.Commons as Commons
import "Tint.js" as Tint

// One activity control: a glyph or short label in a bordered chip, built on
// HoverButton (hover, pressed, cursor, hint). A control whose capability is
// off is disabled: dimmed, no hover, no hint. Clicking never raises the
// card's keyboard focus (KTD4); the parent only receives `clicked`.
HoverButton {
  id: btn

  property string label: ""
  property bool available: true
  property bool emphasized: false
  property color accent: Commons.Color.accent

  // The emphasized fill is the menu's selected background laid over the popup
  // background. An art-derived accent that does not reach 3:1 on it falls
  // back to the menu's selected-text color.
  readonly property color fill: Qt.tint(Commons.Color.popups.background, Commons.Color.menu.selectedBackground)
  readonly property color labelInk: Tint.contrast({ r: btn.accent.r, g: btn.accent.g, b: btn.accent.b },
                                                  { r: btn.fill.r, g: btn.fill.g, b: btn.fill.b }) >= 3
    ? btn.accent : Commons.Color.menu.selectedText

  enabled: btn.available
  selected: btn.emphasized
  outlined: true
  selectedBorder: btn.labelInk
  implicitWidth: Math.max(Commons.Style.spacing.controlHeight, labelText.implicitWidth + Commons.Style.spacing.huge)
  implicitHeight: Commons.Style.spacing.controlHeight

  Txt {
    id: labelText
    text: btn.label
    color: btn.emphasized ? btn.labelInk : Commons.Color.popups.text
    anchors.centerIn: parent
  }
}
