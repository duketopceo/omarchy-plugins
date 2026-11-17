import QtQuick 6.11
import qs.Commons as Commons
import "More.js" as More
import "Glyphs.js" as Glyphs

// Messages: Blip's unread chats as tiles in two columns: an avatar circle
// (initials, or a person glyph for a chat with no name), the chat name and an
// unread badge. A summary pill and Open Blip sit on top. Clicking a tile opens
// that chat through the root's openBlipChat(), which only passes ids Blip's
// own toast would accept. Muted chats are dimmed with an outlined badge.
// Counts only: message text is never read (More.js).
Item {
  id: page

  property var island: null
  property int maxRows: 0

  readonly property var rows: page.island ? page.island.messages.rows : []
  readonly property int unread: page.island ? page.island.messages.unread : 0
  readonly property int cols: 2
  readonly property int maxList: 6
  readonly property int gap: Commons.Style.spacing.lg
  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int tileH: Commons.Style.space(52)

  function count() { return Math.min(page.maxList, page.rows.length) }
  function heightFor(n) {
    var r = Math.ceil(Math.max(1, n) / page.cols)
    return page.rowH + page.gap + r * page.tileH + (r - 1) * page.gap
  }

  Column {
    width: parent.width
    spacing: page.gap

    Item {
      width: parent.width
      height: page.rowH

      Tag {
        id: summary
        anchors.verticalCenter: parent.verticalCenter
        visible: page.unread > 0
        tone: Commons.Color.accent
        text: page.unread + " unread"
      }

      HoverButton {
        id: openBlip
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        outlined: true
        radius: height / 2
        width: openRow.implicitWidth + Commons.Style.spacing.huge * 2
        height: page.rowH
        hint: "Open Blip"
        onClicked: if (page.island) page.island.openBlip()

        Row {
          id: openRow
          anchors.centerIn: parent
          spacing: Commons.Style.spacing.lg

          Txt {
            icon: true
            anchors.verticalCenter: parent.verticalCenter
            text: Glyphs.GLYPHS.open
          }
          Txt {
            anchors.verticalCenter: parent.verticalCenter
            text: "Open Blip"
          }
        }
      }
    }

    Grid {
      id: grid
      width: parent.width
      columns: page.cols
      columnSpacing: page.gap
      rowSpacing: page.gap
      visible: page.rows.length > 0
      readonly property int tileW: Math.floor((width - page.gap * (page.cols - 1)) / page.cols)

      Repeater {
        model: page.rows.slice(0, Math.max(0, page.maxRows))

        Item {
          id: cell
          required property var modelData
          readonly property bool muted: cell.modelData.muted === true
          width: grid.tileW
          height: page.tileH

          Plate {
            anchors.fill: parent
            opacity: cell.muted ? 0.6 : 1
          }

          HoverButton {
            anchors.fill: parent
            hint: "Open this chat in Blip"
            radius: Commons.Style.cornerRadius + Commons.Style.spacing.xxl
            onClicked: if (page.island) page.island.openBlipChat(cell.modelData.chat)

            Rectangle {
              id: avatar
              width: Commons.Style.space(34)
              height: width
              radius: width / 2
              x: Commons.Style.spacing.xl
              anchors.verticalCenter: parent.verticalCenter
              color: Qt.alpha(Commons.Color.popups.text, 0.12)
              opacity: cell.muted ? 0.6 : 1

              Txt {
                anchors.centerIn: parent
                width: implicitWidth
                font.bold: true
                visible: cell.modelData.initials !== ""
                text: cell.modelData.initials
              }
              Txt {
                icon: true
                anchors.centerIn: parent
                width: implicitWidth
                font.pixelSize: Commons.Style.font.heading
                visible: cell.modelData.initials === ""
                text: Glyphs.GLYPHS.person
              }
            }

            Txt {
              anchors.left: avatar.right
              anchors.leftMargin: Commons.Style.spacing.xl
              anchors.right: badge.left
              anchors.rightMargin: Commons.Style.spacing.lg
              anchors.verticalCenter: parent.verticalCenter
              muted: cell.muted
              text: cell.modelData.label
            }

            CountBadge {
              id: badge
              anchors.right: parent.right
              anchors.rightMargin: Commons.Style.spacing.xl
              anchors.verticalCenter: parent.verticalCenter
              muted: cell.muted
              text: cell.modelData.badge
            }
          }
        }
      }
    }

    EmptyNote {
      visible: page.rows.length === 0
      width: parent.width
      height: page.tileH
      text: "All caught up"
    }
  }
}
