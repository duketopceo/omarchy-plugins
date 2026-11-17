import QtQuick 6.11
import qs.Commons as Commons
import "Pages.js" as Pages
import "More.js" as More
import "Glyphs.js" as Glyphs

// More: a launcher grid of the pages that are not in the chip row (Shots,
// Messages, Dayflow when detected, and Settings). Each tile is an icon over a
// short name; Messages carries its unread count in a corner badge and Shots a
// dot while there is an unseen screenshot. A live page also shows in the chip
// row while there is room (Pages.js).
Item {
  id: page

  property var island: null
  property var entries: ["settings"]

  signal openPage(string id)

  readonly property int cols: 4
  readonly property int gap: Commons.Style.spacing.lg
  readonly property int tileH: Commons.Style.space(96)
  readonly property int iconSize: Commons.Style.space(44)

  function count() { return page.entries.length }
  function heightFor(n) {
    var r = Math.ceil(Math.max(1, n) / page.cols)
    return r * page.tileH + (r - 1) * page.gap
  }

  // The badge text for a page: Messages' unread count, "" for none.
  function badge(id) {
    var isl = page.island
    return isl && id === "messages" ? More.badgeText(isl.messages.unread) : ""
  }
  // A dot badge: an unseen screenshot.
  function dotted(id) {
    var isl = page.island
    return !!isl && id === "shots" && isl.pageLive.shots === true
  }

  // Tiles are sized for a full row of four and the grid is centered, so a row
  // of three sits in the middle like a launcher.
  Grid {
    id: grid
    anchors.horizontalCenter: parent.horizontalCenter
    columns: Math.min(page.cols, Math.max(1, page.entries.length))
    columnSpacing: page.gap
    rowSpacing: page.gap
    readonly property int tileW: Math.floor((page.width - page.gap * (page.cols - 1)) / page.cols)

    Repeater {
      model: page.entries

      Item {
        id: cell
        required property string modelData
        width: grid.tileW
        height: page.tileH

        Plate {
          anchors.fill: parent
        }

        HoverButton {
          id: item
          anchors.fill: parent
          hint: "Open " + Pages.label(cell.modelData)
          radius: Commons.Style.cornerRadius + Commons.Style.spacing.xxl
          onClicked: page.openPage(cell.modelData)

          Rectangle {
            id: disc
            width: page.iconSize
            height: width
            radius: width / 2
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: Commons.Style.spacing.xxl
            color: Qt.alpha(Commons.Color.popups.text, 0.1)

            Txt {
              icon: true
              anchors.centerIn: parent
              width: implicitWidth
              font.pixelSize: Commons.Style.font.heading + Commons.Style.spacing.md
              text: Glyphs.pageGlyph(cell.modelData)
            }

            CountBadge {
              id: countBadge
              visible: page.badge(cell.modelData) !== "" || page.dotted(cell.modelData)
              text: page.badge(cell.modelData)
              x: parent.width - width * 0.7
              y: -height * 0.3
            }
          }

          Txt {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: disc.bottom
            anchors.topMargin: Commons.Style.spacing.lg
            width: Math.min(implicitWidth, parent.width - Commons.Style.spacing.xxl * 2)
            horizontalAlignment: Text.AlignHCenter
            text: Pages.label(cell.modelData)
          }
        }
      }
    }
  }
}
