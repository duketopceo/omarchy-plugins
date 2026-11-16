import QtQuick 6.11
import qs.Commons as Commons

// The hover hint, drawn once by the Card above every page (HoverButton asks
// for it by walking up to the Card). It never takes the pointer, so it cannot
// become a hover target or steal a click.
Rectangle {
  id: bubble

  property string text: ""
  property int maxWidth: 240

  readonly property int padX: Commons.Style.spacing.md
  readonly property int padY: Commons.Style.spacing.sm

  width: Math.min(bubble.maxWidth, label.implicitWidth + bubble.padX * 2)
  height: label.implicitHeight + bubble.padY * 2
  radius: Commons.Style.cornerRadius
  color: Commons.Color.popups.background
  border.width: Commons.Style.normalBorderWidth
  border.color: Commons.Color.popups.border

  Txt {
    id: label
    anchors.centerIn: parent
    width: bubble.width - bubble.padX * 2
    horizontalAlignment: Text.AlignHCenter
    text: bubble.text
  }
}
