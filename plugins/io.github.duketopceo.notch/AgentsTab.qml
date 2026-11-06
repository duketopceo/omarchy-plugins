import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Agents.js" as Agents

// Expanded-panel tab, laid out like a small menu-bar app: header with totals
// and "Open herdr", AI usage (one row per provider, top 3 + expander), then
// herdr agents grouped by space/machine in collapsible groups. Click an agent
// to focus it in the herdr desktop app. Usage is shared with Notch (fetched at
// most every 5 minutes while the tab is visible).
Item {
  id: tab

  // Root Notch item (N1 tabs contract); AgentsActivity lives there as `agentsActivity`.
  property var notch: null
  property color textColor: notch ? notch.textColor : Tk.text
  property color dimColor: notch ? notch.dimColor : Tk.dim
  property string family: notch ? notch.fontFamily : Commons.Style.font.family

  readonly property var summary: notch && notch.agentsActivity ? notch.agentsActivity.summary : Agents.parseLs("")
  readonly property var usage: notch && notch.usage ? notch.usage : ({ ok: false, providers: [] })
  property real nowMs: Date.now()

  readonly property string home: Quickshell.env("HOME")
  readonly property string iconDir: "file://" + home + "/.config/herdr-app/icons/"

  // ---- remembered state
  property var collapsed: []
  property bool collapsedDirty: false
  property bool usageExpanded: false
  readonly property var stored: notch && notch.shellConfig ? Agents.readCollapsed(notch.shellConfig, notch.pluginId) : []
  onStoredChanged: if (!collapsedDirty) collapsed = stored
  function toggleGroup(g) {
    collapsed = Agents.toggleCollapsed(collapsed, g)
    collapsedDirty = true
    if (notch && typeof notch.setSetting === "function") notch.setSetting("agents.collapsed", collapsed)
  }

  readonly property var groups: Agents.groupModel(summary)
  readonly property var urows: Agents.usageRows(usage, nowMs, usageExpanded, 3)

  readonly property color warnColor: notch && notch.themeObj ? notch.themeObj.warn : Tk.amber
  readonly property color goodColor: notch && notch.themeObj ? notch.themeObj.good : Tk.good
  function statusColor(status) {
    var s = Agents.normStatus(status)
    return s === "blocked" ? Tk.urgent : s === "done" ? goodColor : s === "working" ? Tk.accent : Tk.dim
  }
  function sevColor(sev) {
    return sev === "critical" ? Tk.urgent : sev === "warn" ? warnColor : goodColor
  }

  function refreshUsage() {
    tab.nowMs = Date.now()
    if (notch) notch.refreshUsage()
  }
  onVisibleChanged: if (visible) refreshUsage()
  onNotchChanged: if (visible) refreshUsage()
  Timer { interval: 30000; running: tab.visible; repeat: true; onTriggered: tab.refreshUsage() }
  Component.onCompleted: if (visible) refreshUsage()

  Process { id: focusProc }
  function focusAgent(terminal) {
    focusProc.command = [tab.home + "/.local/bin/herdr-app", "do", "agent.focus", "--terminal", terminal]
    focusProc.running = true
  }
  Process { id: openProc; command: [tab.home + "/.local/bin/herdr-app"] }

  // A monogram badge, or herdr's own icon when it has one for this app.
  component AppIcon: Item {
    id: ic
    property var info: ({ file: "", monogram: "?", color: tab.dimColor })
    property int size: 16
    width: size; height: size
    Image {
      id: img
      anchors.fill: parent
      visible: status === Image.Ready
      source: ic.info.file ? tab.iconDir + ic.info.file : ""
      sourceSize.width: ic.size * 2
      sourceSize.height: ic.size * 2
      fillMode: Image.PreserveAspectFit
      asynchronous: true
    }
    Rectangle {
      anchors.fill: parent
      visible: img.status !== Image.Ready
      radius: Tk.r(ic.size * 0.28)
      color: Qt.rgba(Qt.color(ic.info.color).r, Qt.color(ic.info.color).g, Qt.color(ic.info.color).b, 0.22)
      Text {
        anchors.centerIn: parent
        text: ic.info.monogram
        color: ic.info.color
        font.family: tab.family
        font.pixelSize: ic.size * 0.62
        font.weight: Font.Bold
        textFormat: Text.PlainText
      }
    }
  }

  ColumnLayout {
    id: head
    anchors { left: parent.left; right: parent.right; top: parent.top }
    spacing: 0

    // ---- header
    Item {
      Layout.fillWidth: true
      implicitHeight: 24
      Text {
        id: totals
        anchors.verticalCenter: parent.verticalCenter
        text: Agents.totalsText(tab.summary)
        color: tab.textColor
        font.family: tab.family
        font.pixelSize: 12
        font.weight: Font.DemiBold
        textFormat: Text.PlainText
      }
      Text {
        anchors.left: totals.right
        anchors.leftMargin: 8
        anchors.right: openBtn.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: Agents.countsText(tab.summary.counts)
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 11
        textFormat: Text.PlainText
        elide: Text.ElideRight
      }
      Rectangle {
        id: openBtn
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: openLbl.implicitWidth + 16
        height: 20
        radius: Tk.r(10)
        color: Tk.tint(openHit.containsMouse ? 0.16 : 0.08)
        Text {
          id: openLbl
          anchors.centerIn: parent
          text: "Open herdr"
          color: tab.textColor
          font.family: tab.family
          font.pixelSize: 11
          textFormat: Text.PlainText
        }
        MouseArea {
          id: openHit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: openProc.running = true
        }
      }
    }
  }

  NotchScroll {
    anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; topMargin: 2 }
    rowHeight: 26
    contentWidth: width
    contentHeight: col.implicitHeight

    ColumnLayout {
      id: col
      width: parent.width
      spacing: 0

      // ---- AI usage
      Repeater {
        model: tab.urows.rows
        delegate: Item {
          id: urow
          required property var modelData
          Layout.fillWidth: true
          implicitHeight: 24

          AppIcon {
            id: uicon
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            size: 14
            info: ({ file: urow.modelData.icon, monogram: urow.modelData.initial, color: urow.modelData.color })
          }
          Text {
            id: uname
            anchors.left: uicon.right
            anchors.leftMargin: 7
            anchors.verticalCenter: parent.verticalCenter
            width: 70
            text: urow.modelData.name
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: 11
            textFormat: Text.PlainText
            elide: Text.ElideRight
          }
          Text {
            id: uright
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: 128
            horizontalAlignment: Text.AlignRight
            text: urow.modelData.percent + "%" + (urow.modelData.resetText ? "  ·  " + urow.modelData.resetText : "")
            color: tab.dimColor
            font.family: tab.family
            font.pixelSize: 10
            textFormat: Text.PlainText
            elide: Text.ElideRight
          }
          SegBar {
            id: track
            anchors.left: uname.right
            anchors.leftMargin: 4
            anchors.right: uright.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            swiftHeight: 4
            track: Tk.tint(0.12)
            value: urow.modelData.percent / 100
            fill: tab.sevColor(urow.modelData.severity)
          }
        }
      }
      Item {
        visible: tab.urows.hidden > 0 || (tab.usageExpanded && tab.urows.total > 3)
        Layout.fillWidth: true
        implicitHeight: 18
        Text {
          anchors.left: parent.left
          anchors.leftMargin: 21
          anchors.verticalCenter: parent.verticalCenter
          text: tab.usageExpanded ? "Show less" : "+" + tab.urows.hidden + " more"
          color: moreHit.containsMouse ? tab.textColor : tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
          textFormat: Text.PlainText
        }
        MouseArea {
          id: moreHit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: tab.usageExpanded = !tab.usageExpanded
        }
      }
      Rectangle {
        visible: tab.urows.rows.length > 0
        Layout.fillWidth: true
        Layout.topMargin: 3
        Layout.bottomMargin: 3
        implicitHeight: 1
        color: Tk.tint(0.08)
      }

      // ---- Agents
      Text {
        visible: tab.summary.total === 0
        Layout.topMargin: 6
        text: "No agents running"
        color: tab.dimColor
        font.family: tab.family
        font.pixelSize: 12
        textFormat: Text.PlainText
      }

      Repeater {
        model: tab.groups
        delegate: ColumnLayout {
          id: grp
          required property var modelData
          readonly property bool folded: Agents.isCollapsed(tab.collapsed, modelData)
          Layout.fillWidth: true
          spacing: 0

          Item {
            Layout.fillWidth: true
            implicitHeight: 22

            Text {
              id: chev
              anchors.left: parent.left
              anchors.leftMargin: 2
              anchors.verticalCenter: parent.verticalCenter
              text: "▸"
              color: tab.dimColor
              font.family: tab.family
              font.pixelSize: 10
              textFormat: Text.PlainText
              rotation: grp.folded ? 0 : 90
              Behavior on rotation { NumberAnimation { duration: Tk.ms(120) } }
            }
            Text {
              id: gname
              anchors.left: chev.right
              anchors.leftMargin: 6
              anchors.verticalCenter: parent.verticalCenter
              width: Math.min(implicitWidth, parent.width * 0.4)
              text: grp.modelData.space
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 11
              font.weight: Font.DemiBold
              textFormat: Text.PlainText
              elide: Text.ElideRight
            }
            Rectangle {
              id: badge
              visible: grp.modelData.machine !== ""
              anchors.left: gname.right
              anchors.leftMargin: 6
              anchors.verticalCenter: parent.verticalCenter
              width: visible ? mtxt.implicitWidth + 10 : 0
              height: 14; radius: Tk.r(7)
              color: Tk.tint(0.10)
              Text {
                id: mtxt
                anchors.centerIn: parent
                text: grp.modelData.machine
                color: tab.dimColor
                font.family: tab.family
                font.pixelSize: 9
                textFormat: Text.PlainText
              }
            }
            Text {
              anchors.left: badge.visible ? badge.right : gname.right
              anchors.leftMargin: 8
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              horizontalAlignment: Text.AlignRight
              text: grp.modelData.countsText
              color: grp.modelData.blocked ? Tk.urgent : tab.dimColor
              font.family: tab.family
              font.pixelSize: 10
              textFormat: Text.PlainText
              elide: Text.ElideLeft
            }
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: tab.toggleGroup(grp.modelData)
            }
          }

          Repeater {
            model: grp.folded ? [] : grp.modelData.agents
            delegate: Item {
              id: row
              required property var modelData
              readonly property color sc: tab.statusColor(modelData.status)
              Layout.fillWidth: true
              implicitHeight: 26

              Rectangle {
                anchors.fill: parent
                radius: Tk.r(6)
                color: Tk.text
                opacity: hit.containsMouse ? 0.10 : 0
              }
              AppIcon {
                id: aicon
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                size: 16
                info: Agents.iconFor(row.modelData.app)
              }
              Text {
                anchors.left: aicon.right
                anchors.leftMargin: 8
                anchors.right: pill.left
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: row.modelData.tab || row.modelData.appName
                color: tab.textColor
                font.family: tab.family
                font.pixelSize: 12
                textFormat: Text.PlainText
                elide: Text.ElideRight
              }
              Rectangle {
                id: pill
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: plabel.implicitWidth + 14
                height: 16; radius: Tk.r(8)
                color: Tk.alpha(row.sc, 0.20)
                SequentialAnimation on opacity {
                  running: row.modelData.status === "working" && tab.visible
                  loops: Animation.Infinite
                  NumberAnimation { to: 0.55; duration: 900; easing.type: Easing.InOutSine }
                  NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                }
                Text {
                  id: plabel
                  anchors.centerIn: parent
                  text: Agents.statusLabel(row.modelData.status)
                  color: row.sc
                  font.family: tab.family
                  font.pixelSize: 10
                  font.weight: Font.Medium
                  textFormat: Text.PlainText
                }
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
      Item { implicitHeight: 4 }
    }
  }
}
