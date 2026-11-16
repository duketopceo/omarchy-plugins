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

    Text {
      id: summary
      textFormat: Text.PlainText
      text: page.keys.length === 0 ? "No agent sessions" : (Agents.countsText(page.rows) || (page.keys.length + " idle"))
      color: Commons.Color.popups.text
      opacity: 0.75
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
    }

    Column {
      width: parent.width
      spacing: page.gap

      Repeater {
        model: page.keys.slice(0, Math.max(0, page.maxRows))

        Rectangle {
          id: item
          required property string modelData
          readonly property var row: page.rowFor(modelData)
          width: parent.width
          height: page.rowH
          radius: Commons.Style.cornerRadius
          color: hover.containsMouse && item.row && item.row.focusable ? Commons.Color.menu.selectedBackground : "transparent"

          Rectangle {
            id: badge
            width: page.rowH - 8; height: width; radius: width / 2
            x: 2
            anchors.verticalCenter: parent.verticalCenter
            color: "transparent"
            border.width: Commons.Style.normalBorderWidth
            border.color: item.row && item.row.status === "needs" ? Commons.Color.urgent : Commons.Color.menu.border
            Text {
              anchors.centerIn: parent
              textFormat: Text.PlainText
              text: item.row ? item.row.app.charAt(0) : ""
              color: Commons.Color.popups.text
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              font.bold: true
            }
          }

          Text {
            anchors.left: badge.right
            anchors.leftMargin: Commons.Style.spacing.lg
            anchors.right: status.left
            anchors.rightMargin: Commons.Style.spacing.lg
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: item.row ? item.row.app + "  ·  " + item.row.title + (item.row.where && item.row.where !== item.row.title ? "  ·  " + item.row.where : "") : ""
            color: Commons.Color.popups.text
            elide: Text.ElideRight
            maximumLineCount: 1
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
          }

          Text {
            id: status
            anchors.right: parent.right
            anchors.rightMargin: Commons.Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            textFormat: Text.PlainText
            text: item.row ? item.row.statusLabel : ""
            color: item.row && item.row.status === "needs" ? Commons.Color.urgent
                 : (item.row && item.row.status === "working" ? Commons.Color.accent : Commons.Color.popups.text)
            opacity: item.row && (item.row.status === "needs" || item.row.status === "working") ? 1 : 0.6
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
          }

          MouseArea {
            id: hover
            anchors.fill: parent
            hoverEnabled: true
            enabled: item.row !== null && item.row.focusable
            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: if (page.island && item.row) page.island.focusAgent(item.row)
          }
        }
      }
    }
  }
}
