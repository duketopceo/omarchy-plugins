import QtQuick 6.11
import Quickshell.Widgets
import qs.Commons as Commons

// Shots: the captioned screenshots as a grid of rounded thumbnails, newest
// first, as many as fit the card's fixed height (two rows of four). Each
// thumbnail is decoded small and asynchronously; clicking one opens the
// picture through the root's openShot(), which re-checks the name. The caption
// is the hover hint. With none, one centered empty line.
Item {
  id: page

  property var island: null
  property int maxRows: 0

  readonly property int cols: 4
  readonly property int cap: 8
  readonly property int gap: Commons.Style.spacing.lg
  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int tileH: Commons.Style.space(88)
  readonly property var rows: page.island ? page.island.shotRows : []
  readonly property int total: page.island && page.island.shots ? page.island.shots.total : 0

  function count() { return Math.min(page.cap, page.rows.length) }
  function heightFor(n) {
    if (n <= 0) return page.rowH + page.gap
    var r = Math.ceil(n / page.cols)
    return page.rowH + page.gap + r * page.tileH + (r - 1) * page.gap
  }

  Column {
    width: parent.width
    spacing: page.gap
    visible: page.rows.length > 0

    Item {
      width: parent.width
      height: page.rowH

      Txt {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        kind: "caption"
        text: page.total + " captioned screenshots"
      }
    }

    Grid {
      id: grid
      columns: page.cols
      columnSpacing: page.gap
      rowSpacing: page.gap
      readonly property int tileW: Math.floor((page.width - page.gap * (page.cols - 1)) / page.cols)

      Repeater {
        model: page.rows.slice(0, Math.max(0, page.maxRows))

        Item {
          id: cell
          required property var modelData
          width: grid.tileW
          height: page.tileH

          ClippingRectangle {
            id: frame
            anchors.fill: parent
            radius: Commons.Style.cornerRadius + Commons.Style.spacing.xxl
            color: Qt.alpha(Commons.Color.popups.text, 0.06)

            Image {
              anchors.fill: parent
              source: page.island ? page.island.shotUrl(cell.modelData.name) : ""
              asynchronous: true
              cache: true
              fillMode: Image.PreserveAspectCrop
              sourceSize.width: 320
              sourceSize.height: 200
              opacity: status === Image.Ready ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: Commons.Style.duration(160) } }
            }
          }

          HoverButton {
            anchors.fill: parent
            z: 1
            radius: frame.radius
            hint: cell.modelData.label !== "" ? cell.modelData.label : "Open this screenshot"
            onClicked: if (page.island) page.island.openShot(cell.modelData.name)
          }
        }
      }
    }
  }

  EmptyNote {
    visible: page.rows.length === 0
    width: parent.width
    height: page.rowH + page.gap
    text: "No captioned screenshots yet"
  }
}
