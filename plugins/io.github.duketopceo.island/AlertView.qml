import QtQuick 6.11
import qs.Commons as Commons

// A transient alert's content (R4, KTD7): a glyph, or a level ring when the
// alert carries a level (charging), then the title over the detail, each one
// line and elided. The window fixes the size; long strings never change it.
Item {
  id: view

  // Alert.current() output: { kind, title, detail, glyph, level }.
  property var alert: null
  property color textColor: Commons.Color.popups.text
  property color accent: Commons.Color.accent

  readonly property int pad: Commons.Style.spacing.huge
  readonly property int iconSize: Math.max(0, height - pad * 2)
  readonly property bool hasLevel: view.alert !== null && typeof view.alert.level === "number"

  Item {
    id: icon
    x: view.pad
    width: view.iconSize
    height: view.iconSize
    anchors.verticalCenter: parent.verticalCenter

    Canvas {
      id: ring
      anchors.fill: parent
      visible: view.hasLevel
      readonly property real level: view.hasLevel ? Math.max(0, Math.min(1, view.alert.level)) : 0
      onLevelChanged: requestPaint()
      onVisibleChanged: requestPaint()
      onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        var r = Math.min(width, height) / 2 - 3
        ctx.lineWidth = 4
        ctx.lineCap = "round"
        ctx.strokeStyle = Qt.rgba(view.textColor.r, view.textColor.g, view.textColor.b, 0.25)
        ctx.beginPath(); ctx.arc(width / 2, height / 2, r, 0, Math.PI * 2); ctx.stroke()
        ctx.strokeStyle = view.accent
        ctx.beginPath(); ctx.arc(width / 2, height / 2, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * ring.level); ctx.stroke()
      }
    }

    Text {
      anchors.centerIn: parent
      textFormat: Text.PlainText
      text: view.alert ? view.alert.glyph : ""
      color: view.hasLevel ? view.accent : view.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: view.hasLevel ? Commons.Style.font.body : Commons.Style.font.displayLarge
    }
  }

  Column {
    anchors.left: icon.right
    anchors.leftMargin: Commons.Style.spacing.huge
    anchors.right: parent.right
    anchors.rightMargin: view.pad
    anchors.verticalCenter: parent.verticalCenter
    spacing: Commons.Style.spacing.sm

    Text {
      width: parent.width
      textFormat: Text.PlainText
      text: view.alert ? view.alert.title : ""
      color: view.textColor
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.heading
      font.bold: true
      elide: Text.ElideRight
      maximumLineCount: 1
    }
    Text {
      width: parent.width
      textFormat: Text.PlainText
      text: view.alert ? view.alert.detail : ""
      color: view.textColor
      opacity: 0.8
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.body
      elide: Text.ElideRight
      maximumLineCount: 1
    }
  }
}
