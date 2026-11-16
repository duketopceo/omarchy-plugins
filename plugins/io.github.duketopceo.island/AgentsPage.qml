import QtQuick 6.11
import qs.Commons as Commons
import "Agents.js" as Agents

// Agents: herdr and Claude Code sessions, the ones that need Luke first.
// Clicking a session with a window focuses its terminal through Hyprland
// (and herdr's own terminal focus for herdr sessions). Approve/deny is not
// here: it needs a hook socket (follow-up).
Item {
  id: page

  property var island: null
  property int maxRows: 0

  readonly property int maxList: 7
  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int gap: Commons.Style.spacing.sm
  readonly property var rows: page.island ? page.island.agentRows : []

  // Keyed on session ids, reassigned only when the set or order changes, so
  // a poll does not rebuild the row under a click.
  property var keys: []
  onRowsChanged: {
    var k = []
    for (var i = 0; i < page.rows.length; i++) k.push(page.rows[i].key)
    if (k.join(",") !== page.keys.join(",")) page.keys = k
  }
  function rowFor(key) {
    for (var i = 0; i < page.rows.length; i++) if (page.rows[i].key === key) return page.rows[i]
    return null
  }

  function count() { return Math.min(page.maxList, page.keys.length) }
  function heightFor(n) { return summary.implicitHeight + Commons.Style.spacing.lg + Math.max(1, n) * (page.rowH + page.gap) }

  Column {
    width: parent.width
    spacing: Commons.Style.spacing.lg

    Txt {
      id: summary
      width: parent.width
      readonly property int hidden: Math.max(0, page.keys.length - page.maxRows)
      kind: "caption"
      text: (page.keys.length === 0 ? "Agent sessions" : (Agents.countsText(page.rows) || (page.keys.length + " idle")))
            + (hidden > 0 ? "  ·  " + hidden + " more not shown" : "")
    }

    EmptyNote {
      visible: page.keys.length === 0
      width: parent.width
      height: page.rowH + page.gap
      text: "No agent sessions"
    }

    Column {
      width: parent.width
      spacing: page.gap

      Repeater {
        model: page.keys.slice(0, Math.max(0, page.maxRows))

        HoverButton {
          id: item
          required property string modelData
          readonly property var row: page.rowFor(modelData)
          passive: !(item.row !== null && item.row.focusable)
          hint: item.row && item.row.focusable ? "Focus this session's terminal" : ""
          width: parent.width
          height: page.rowH
          onClicked: if (page.island && item.row) page.island.focusAgent(item.row)

          Rectangle {
            id: badge
            width: page.rowH - 8; height: width; radius: width / 2
            x: 2
            anchors.verticalCenter: parent.verticalCenter
            color: "transparent"
            border.width: Commons.Style.normalBorderWidth
            border.color: item.row && item.row.status === "needs" ? Commons.Color.urgent : Commons.Color.menu.border
            Txt {
              anchors.centerIn: parent
              width: implicitWidth
              kind: "caption"
              font.bold: true
              opacity: 1
              text: item.row ? item.row.app.charAt(0) : ""
            }
          }

          Txt {
            anchors.left: badge.right
            anchors.leftMargin: Commons.Style.spacing.lg
            anchors.right: status.left
            anchors.rightMargin: Commons.Style.spacing.lg
            anchors.verticalCenter: parent.verticalCenter
            text: item.row ? item.row.app + "  ·  " + item.row.title + (item.row.where && item.row.where !== item.row.title ? "  ·  " + item.row.where : "") : ""
          }

          Txt {
            id: status
            anchors.right: parent.right
            anchors.rightMargin: Commons.Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            kind: "caption"
            text: item.row ? item.row.statusLabel : ""
            color: item.row && item.row.status === "needs" ? Commons.Color.urgent
                 : (item.row && item.row.status === "working" ? Commons.Color.accent : Commons.Color.popups.text)
            opacity: item.row && (item.row.status === "needs" || item.row.status === "working") ? 1 : 0.6
          }
        }
      }
    }
  }
}
