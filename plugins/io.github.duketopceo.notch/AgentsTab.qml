import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Agents.js" as Agents

// Expanded-panel tab: herdr agents grouped by space and machine, then AI
// usage bars. Click an agent to focus it in the herdr desktop app. Usage is
// fetched only while the tab is visible, at most every 5 minutes.
Item {
  id: tab

  // Root Notch item (N1 tabs contract); AgentsActivity lives there as `agentsActivity`.
  property var notch: null
  property color textColor: Commons.Color.foreground
  property color dimColor: Commons.Color.muted
  property string family: Commons.Style.font.family

  readonly property var summary: notch && notch.agentsActivity ? notch.agentsActivity.summary : Agents.parseLs("")
  property var usage: ({ ok: false, providers: [] })
  property real nowMs: Date.now()
  property real lastUsageAt: 0

  readonly property string home: Quickshell.env("HOME")
  readonly property int usageMinGapMs: 5 * 60 * 1000

  function dotColor(status) {
    var k = Agents.statusColorKey(status)
    return k === "warn" ? "#f5a742" : k === "good" ? "#6fbf73" : k === "accent" ? Commons.Color.accent : Commons.Color.muted
  }
  function barColor(sev) {
    return sev === "critical" ? Commons.Color.urgent : sev === "high" ? "#f5a742" : sev === "mid" ? "#e3c867" : "#6fbf73"
  }

  function refreshUsage() {
    var now = Date.now()
    tab.nowMs = now
    if (usageProc.running || now - tab.lastUsageAt < tab.usageMinGapMs) return
    tab.lastUsageAt = now
    usageProc.running = true
  }
  onVisibleChanged: if (visible) refreshUsage()
  // While visible, re-check every 30 s; the gap check keeps fetches to one per 5 min.
  Timer { interval: 30000; running: tab.visible; repeat: true; onTriggered: tab.refreshUsage() }
  Component.onCompleted: if (visible) refreshUsage()

  Process {
    id: usageProc
    command: [tab.home + "/.local/bin/ai-usagebar-omaseal", "usage", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text && text.length < 500000) tab.usage = Agents.parseUsage(text)
    }
  }

  Process { id: focusProc }
  function focusAgent(terminal) {
    focusProc.command = [tab.home + "/.local/bin/herdr-app", "do", "agent.focus", "--terminal", terminal]
    focusProc.running = true
  }

  Flickable {
    anchors.fill: parent
    contentWidth: width
    contentHeight: col.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
      id: col
      width: parent.width
      spacing: 6

      Text {
        visible: tab.summary.total === 0
        text: "No agents running"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 12
        textFormat: Text.PlainText
      }

      Repeater {
        model: tab.summary.groups
        delegate: ColumnLayout {
          id: grp
          required property var modelData
          Layout.fillWidth: true
          spacing: 2

          Text {
            Layout.fillWidth: true
            text: grp.modelData.space + (grp.modelData.machine ? "  ·  " + grp.modelData.machine : "")
            color: tab.dimColor
            font.family: tab.family
            font.pixelSize: 11
            font.weight: Font.DemiBold
            textFormat: Text.PlainText
            elide: Text.ElideRight
          }

          Repeater {
            model: grp.modelData.agents
            delegate: Item {
              id: row
              required property var modelData
              Layout.fillWidth: true
              implicitHeight: 20

              Rectangle {
                anchors.fill: parent
                radius: 4
                color: Commons.Color.foreground
                opacity: hit.containsMouse ? 0.10 : 0
              }
              Rectangle {
                id: dot
                width: 8; height: 8; radius: 4
                anchors.left: parent.left
                anchors.leftMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                color: tab.dotColor(row.modelData.status)
              }
              Text {
                anchors.left: dot.right
                anchors.leftMargin: 8
                anchors.right: stat.left
                anchors.verticalCenter: parent.verticalCenter
                text: row.modelData.appName + (row.modelData.tab ? "  " + row.modelData.tab : "")
                color: tab.textColor
                font.family: tab.family
                font.pixelSize: 12
                textFormat: Text.PlainText
                elide: Text.ElideRight
              }
              Text {
                id: stat
                anchors.right: parent.right
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: row.modelData.status
                color: tab.dotColor(row.modelData.status)
                font.family: tab.family
                font.pixelSize: 11
                textFormat: Text.PlainText
              }
              MouseArea {
                id: hit
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: tab.focusAgent(row.modelData.terminal)
              }
            }
          }
        }
      }

      // ---- AI usage
      Text {
        visible: tab.usage.providers.length > 0
        Layout.topMargin: 6
        text: "AI usage"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 11
        font.weight: Font.DemiBold
        textFormat: Text.PlainText
      }

      Repeater {
        model: tab.usage.providers
        delegate: ColumnLayout {
          id: prov
          required property var modelData
          Layout.fillWidth: true
          spacing: 2

          Repeater {
            model: prov.modelData.rows
            delegate: Item {
              id: urow
              required property var modelData
              Layout.fillWidth: true
              implicitHeight: 16

              Text {
                id: ulabel
                width: 96
                anchors.verticalCenter: parent.verticalCenter
                text: prov.modelData.name + " " + urow.modelData.label
                color: tab.textColor
                font.family: tab.family
                font.pixelSize: 11
                textFormat: Text.PlainText
                elide: Text.ElideRight
              }
              Rectangle {
                id: track
                anchors.left: ulabel.right
                anchors.leftMargin: 6
                anchors.right: upct.left
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                height: 5; radius: 2
                color: Commons.Color.muted
                opacity: 0.35
              }
              Rectangle {
                x: track.x
                anchors.verticalCenter: parent.verticalCenter
                width: Math.round(track.width * urow.modelData.percent / 100)
                height: 5; radius: 2
                color: tab.barColor(urow.modelData.severity)
              }
              Text {
                id: upct
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 74
                horizontalAlignment: Text.AlignRight
                text: urow.modelData.percent + "%" + (urow.modelData.resetAt ? " · " + Agents.resetIn(urow.modelData.resetAt, tab.nowMs) : "")
                color: tab.dimColor
                font.family: tab.family
                font.pixelSize: 11
                textFormat: Text.PlainText
              }
            }
          }
        }
      }
    }
  }
}
