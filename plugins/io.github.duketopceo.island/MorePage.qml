import QtQuick 6.11
import qs.Commons as Commons
import "Pages.js" as Pages
import "More.js" as More

// More: the pages that are not in the chip row (Shots, Messages, Dayflow when
// detected, and Settings), each with a one-line status. A live page also
// shows in the chip row while there is room (Pages.js).
Item {
  id: page

  property var island: null
  property var entries: ["settings"]

  signal openPage(string id)

  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int gap: Commons.Style.spacing.sm

  function count() { return page.entries.length }
  function heightFor(n) { return Math.max(1, n) * (page.rowH + page.gap) }

  function detail(id) {
    var isl = page.island
    if (!isl) return ""
    if (id === "messages") return More.unreadText(isl.messages.unread)
    if (id === "dayflow") return More.dayflowState(isl.dayflow)
    if (id === "shots") return isl.pageLive.shots ? "New screenshot" : (isl.shots ? isl.shots.total + " captioned" : "")
    if (id === "settings") return "Island settings"
    return ""
  }

  Column {
    width: parent.width
    spacing: page.gap

    Repeater {
      model: page.entries

      Rectangle {
        id: item
        required property string modelData
        width: parent.width
        height: page.rowH
        radius: Commons.Style.cornerRadius
        color: hover.containsMouse ? Commons.Color.menu.selectedBackground : "transparent"

        Text {
          id: name
          anchors.left: parent.left
          anchors.leftMargin: Commons.Style.spacing.md
          anchors.verticalCenter: parent.verticalCenter
          textFormat: Text.PlainText
          text: Pages.label(item.modelData)
          color: Commons.Color.popups.text
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
        }
        Text {
          anchors.left: name.right
          anchors.leftMargin: Commons.Style.spacing.huge
          anchors.right: chevron.left
          anchors.rightMargin: Commons.Style.spacing.lg
          anchors.verticalCenter: parent.verticalCenter
          textFormat: Text.PlainText
          text: page.detail(item.modelData)
          color: Commons.Color.popups.text
          opacity: 0.65
          elide: Text.ElideRight
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
        Text {
          id: chevron
          anchors.right: parent.right
          anchors.rightMargin: Commons.Style.spacing.md
          anchors.verticalCenter: parent.verticalCenter
          textFormat: Text.PlainText
          text: "›"
          color: Commons.Color.popups.text
          opacity: 0.6
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.heading
        }
        MouseArea {
          id: hover
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: page.openPage(item.modelData)
        }
      }
    }
  }
}
