import QtQuick 6.11
import Quickshell
import qs.Commons as Commons
import "Agents.js" as Agents
import "Glyphs.js" as Glyphs

// Agents: herdr and Claude Code sessions as a grid of tiles, the ones that
// need Luke first (Agents.js orders and collapses them). Each tile shows the
// app's icon (a lettered circle when the theme has none), the session name,
// its host, and one status mark: a solid urgent dot for needs-you, a pulsing
// accent dot for working, a check for done, a dim dot for idle. Clicking a
// tile with a window focuses its terminal through Hyprland (and herdr's own
// terminal focus for herdr sessions). Approve/deny is not here: it needs a
// hook socket (follow-up).
Item {
  id: page

  property var island: null
  property int maxRows: 0

  readonly property int cols: 3
  readonly property int cap: 6
  readonly property int gap: Commons.Style.spacing.lg
  readonly property int tileH: Commons.Style.space(64)
  readonly property int headerH: Commons.Style.space(22)
  readonly property var rows: page.island ? page.island.agentRows : []
  readonly property var pills: Agents.pills(page.rows)

  // Keyed on session ids, reassigned only when the set or order changes, so
  // a poll does not rebuild a tile under a click. "" is the "+N idle" tile.
  property var keys: []
  property var more: null
  onRowsChanged: {
    var lay = Agents.tiles(page.rows, page.cap)
    var k = []
    for (var i = 0; i < lay.tiles.length; i++) k.push(lay.tiles[i].key)
    if (lay.more) k.push("")
    if (k.join(",") !== page.keys.join(",")) page.keys = k
    page.more = lay.more
  }
  function rowFor(key) {
    for (var i = 0; i < page.rows.length; i++) if (page.rows[i].key === key) return page.rows[i]
    return null
  }

  function count() { return page.keys.length }
  function heightFor(n) {
    if (n <= 0) return page.tileH
    var r = Math.ceil(n / page.cols)
    return page.headerH + page.gap + r * page.tileH + (r - 1) * page.gap
  }

  // The app's icon from the icon theme, or a lettered circle.
  component AgentIcon: Item {
    id: icon
    property string app: ""
    property string letter: ""
    readonly property string src: {
      var names = Agents.iconNames(icon.app)
      for (var i = 0; i < names.length; i++) {
        var p = Quickshell.iconPath(names[i], true)
        if (p) return p
      }
      return ""
    }

    Image {
      visible: icon.src !== ""
      anchors.fill: parent
      source: icon.src
      sourceSize.width: width * 2
      sourceSize.height: height * 2
      fillMode: Image.PreserveAspectFit
      smooth: true
    }
    Rectangle {
      visible: icon.src === ""
      anchors.fill: parent
      radius: width / 2
      color: Qt.alpha(Commons.Color.popups.text, 0.12)
      Txt {
        anchors.centerIn: parent
        width: implicitWidth
        font.bold: true
        text: icon.letter
      }
    }
  }

  // One status mark, top right of a tile.
  component Mark: Item {
    id: mark
    property string status: "idle"
    property bool shown: true
    width: Commons.Style.space(14)
    height: width

    Rectangle {
      id: dot
      visible: mark.status !== "done"
      anchors.centerIn: parent
      width: mark.status === "idle" ? Commons.Style.spacing.lg : Commons.Style.spacing.xl
      height: width
      radius: width / 2
      color: mark.status === "needs" ? Commons.Color.urgent
           : (mark.status === "working" ? Commons.Color.accent : Qt.alpha(Commons.Color.popups.text, 0.3))

      SequentialAnimation on opacity {
        running: mark.status === "working" && mark.shown && Commons.Style.duration(800) > 0
        loops: Animation.Infinite
        NumberAnimation { to: 0.35; duration: Commons.Style.duration(800); easing.type: Easing.InOutSine }
        NumberAnimation { to: 1; duration: Commons.Style.duration(800); easing.type: Easing.InOutSine }
        onStopped: dot.opacity = 1
      }
    }
    Txt {
      visible: mark.status === "done"
      anchors.centerIn: parent
      icon: true
      width: implicitWidth
      text: Glyphs.GLYPHS.check
    }
  }

  Column {
    width: parent.width
    spacing: page.gap
    visible: page.keys.length > 0

    Row {
      id: header
      height: page.headerH
      spacing: Commons.Style.spacing.md

      Repeater {
        model: page.pills

        Tag {
          required property var modelData
          text: modelData.label
          mark: modelData.status === "done" ? "check" : "dot"
          tone: modelData.status === "needs" ? Commons.Color.urgent : Commons.Color.accent
        }
      }
      Tag {
        visible: page.pills.length === 0
        dim: true
        tone: Qt.alpha(Commons.Color.popups.text, 0.4)
        text: page.rows.length + (page.rows.length === 1 ? " idle agent" : " idle agents")
      }
    }

    Grid {
      id: grid
      columns: page.cols
      columnSpacing: page.gap
      rowSpacing: page.gap
      readonly property int tileW: Math.floor((page.width - page.gap * (page.cols - 1)) / page.cols)

      Repeater {
        model: page.keys.slice(0, Math.max(0, page.maxRows))

        Item {
          id: cell
          required property string modelData
          readonly property bool isMore: cell.modelData === ""
          readonly property var row: cell.isMore ? null : page.rowFor(cell.modelData)
          readonly property string status: cell.row ? cell.row.status : "idle"
          width: grid.tileW
          height: page.tileH

          Plate {
            anchors.fill: parent
            opacity: cell.isMore ? 0.5 : (cell.status === "idle" ? 0.7 : 1)
          }

          // Only a tile with a window or terminal to focus is a button; the
          // others are display-only and have no hover, cursor or hint.
          HoverButton {
            anchors.fill: parent
            z: 1
            visible: cell.row !== null && cell.row.focusable
            hint: cell.row && cell.row.status === "needs" ? "Needs you. Focus this session" : "Focus this session's terminal"
            radius: Commons.Style.cornerRadius + Commons.Style.spacing.xxl
            onClicked: if (page.island && cell.row) page.island.focusAgent(cell.row)
          }

          Item {
            id: item
            anchors.fill: parent

            // ---- an agent ----
            AgentIcon {
              id: appIcon
              visible: !cell.isMore
              x: Commons.Style.spacing.xxl
              anchors.verticalCenter: parent.verticalCenter
              width: Commons.Style.space(32)
              height: width
              app: cell.row ? cell.row.appKey : ""
              letter: cell.row ? Agents.initial(cell.row.app) : ""
              opacity: cell.status === "idle" ? 0.6 : 1
            }
            Column {
              visible: !cell.isMore
              anchors.left: appIcon.right
              anchors.leftMargin: Commons.Style.spacing.xl
              anchors.right: parent.right
              anchors.rightMargin: Commons.Style.spacing.xxl + Commons.Style.space(14)
              anchors.verticalCenter: parent.verticalCenter
              spacing: Commons.Style.spacing.xxs

              Txt {
                width: parent.width
                kind: "heading"
                font.pixelSize: Commons.Style.font.title
                opacity: cell.status === "idle" ? 0.6 : 1
                text: cell.row ? cell.row.title : ""
              }
              Txt {
                width: parent.width
                kind: "caption"
                text: cell.row ? (cell.row.host !== "" && cell.row.host !== cell.row.title ? cell.row.host : cell.row.app) : ""
              }
            }
            Mark {
              visible: !cell.isMore
              status: cell.status
              shown: page.visible
              anchors.right: parent.right
              anchors.rightMargin: Commons.Style.spacing.xl
              anchors.top: parent.top
              anchors.topMargin: Commons.Style.spacing.xl
            }

            // ---- the "+N idle" tile ----
            Txt {
              visible: cell.isMore
              anchors.centerIn: parent
              width: implicitWidth
              kind: "heading"
              opacity: 0.6
              text: page.more ? page.more.label : ""
            }
          }
        }
      }
    }
  }

  EmptyNote {
    visible: page.keys.length === 0
    width: parent.width
    height: page.tileH
    text: "No agent sessions"
  }
}
