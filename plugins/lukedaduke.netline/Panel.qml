import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Network lineage glyph. The number IS the signal: dim when nothing is
// flagged, accent when something is. Click opens the panel; the panel opens
// the full arc map in the browser.
// All numbers come from bin/status.py, which reads the netline store
// read-only. This file never touches the network or the daemon.
Panel {
  id: root
  moduleName: "lukedaduke.netline"
  ipcTarget: "lukedaduke.netline"

  property bool statusKnown: false
  property bool live: false
  property int flagCount: 0
  property var flagged: []
  property var topDests: []
  property string bytesIn: "—"
  property string bytesOut: "—"
  property string lastError: ""
  property bool opening: false
  property var agents: []
  property bool agentsKnown: false

  readonly property color foreground: bar ? bar.foreground : Commons.Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color urgent: Commons.Color.urgent
  readonly property color accent: Commons.Color.accent
  readonly property color good: Commons.Color.accent
  readonly property color glyphColor: !statusKnown ? dim : flagCount > 0 ? urgent : (live ? accent : dim)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }
  readonly property string py: "/usr/bin/python3"
  readonly property var procEnv: ({ "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8" })

  function fillFor(c, alpha) { return Qt.rgba(c.r, c.g, c.b, alpha) }

  function refresh() {
    if (statusProc.running) return
    statusProc.running = true
    statusDeadline.restart()
  }

  function applyStatus(data) {
    if (!data || typeof data !== "object") return
    if (data.ok !== true) { root.lastError = data.error || "unavailable"; return }
    root.flagCount = (data.flagged || []).length
    root.flagged = data.flagged || []
    root.topDests = data.top || []
    root.live = data.live === true
    root.bytesIn = data.bytes_in || "—"
    root.bytesOut = data.bytes_out || "—"
    root.statusKnown = true
    root.lastError = ""
  }

  function openMap() {
    if (openProc.running) return
    root.opening = true
    openProc.running = true
  }

  function restartNetline() {
    if (restartProc.running) return
    restartProc.running = true
  }

  onOpenedChanged: if (opened) { root.refresh(); root.refreshAgents() }

  Process {
    id: statusProc
    command: [root.py, root.pluginRoot + "/bin/status.py", "status"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        statusDeadline.stop()
        try {
          if (!text || text.trim().length === 0 || text.length > 100000) return
          root.applyStatus(JSON.parse(text))
        } catch (e) {}
      }
    }
    stderr: StdioCollector { waitForEnd: true; onStreamFinished: {} }
    onExited: statusDeadline.stop()
  }

  Process {
    id: openProc
    command: [root.py, root.pluginRoot + "/bin/status.py", "open"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: { root.opening = false; root.close() } }
    stderr: StdioCollector { waitForEnd: true; onStreamFinished: {} }
    onExited: root.opening = false
  }

  Process {
    id: restartProc
    command: ["/bin/sh", root.pluginRoot + "/bin/netline-restart.sh"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: {} }
    stderr: StdioCollector { waitForEnd: true; onStreamFinished: {} }
    onExited: { root.refresh(); restartSettle.restart() }
  }

  Process {
    id: agentsProc
    command: [root.py, root.pluginRoot + "/bin/agents-auth.py", "status"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          if (!text || text.length > 200000) return
          var d = JSON.parse(text)
          if (d && d.ok) { root.agents = d.agents || []; root.agentsKnown = true }
        } catch (e) {}
      }
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  // Probes spawn a dozen CLIs, so they run on panel open, not on a timer.
  function refreshAgents() {
    if (agentsProc.running) return
    agentsProc.running = true
  }

  Timer { id: statusDeadline; interval: 12000; onTriggered: { statusProc.signal(9); root.lastError = "timeout" } }
  Timer { id: statusTimer; interval: 15000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refresh() }
  Timer { id: restartSettle; interval: 3000; onTriggered: root.refresh() }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    // The mark is the map itself: node, arc, node.
    text: "󰕙"
    tooltipText: !root.statusKnown ? "netline · starting"
                 : root.flagCount > 0 ? "netline · " + root.flagCount + " flagged · " + root.bytesIn + " in"
                 : "netline · " + root.bytesIn + " in · " + root.bytesOut + " out"
    active: root.flagCount > 0
    activeColor: root.urgent
    foreground: root.glyphColor
    onPressed: function (b) { root.toggle() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(400), 460)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 460)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()

      Column {
        id: mainColumn
        width: parent.width
        spacing: Style.space(10)

        // ---- header: traffic totals + live dot
        Row {
          width: parent.width
          spacing: Style.space(10)

          Rectangle {
            id: iconTile
            width: Style.space(34); height: Style.space(34)
            radius: Style.cornerRadius
            color: root.fillFor(root.flagCount > 0 ? root.urgent : root.accent, 0.12)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              anchors.centerIn: parent
              text: "󰕙"; textFormat: Text.PlainText
              color: root.glyphColor
              font.family: root.fontFamily; font.pixelSize: Style.font.iconLarge
            }
          }

          Column {
            width: parent.width - iconTile.width - livePill.width - parent.spacing * 2
            spacing: Style.space(2)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              text: "NETLINE"; textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily; font.pixelSize: Style.font.subtitle
              font.bold: true
            }
            Text {
              width: parent.width
              text: root.bytesIn + " in · " + root.bytesOut + " out · 15 min"
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }

          Rectangle {
            id: livePill
            height: Style.space(22)
            width: pillRow.width + Style.space(16)
            radius: height / 2
            color: root.fillFor(root.live ? root.accent : root.dim, 0.15)
            border.color: root.fillFor(root.live ? root.accent : root.dim, 0.4)
            anchors.verticalCenter: parent.verticalCenter
            Row {
              id: pillRow
              anchors.centerIn: parent
              spacing: Style.space(5)
              Rectangle {
                width: Style.space(5); height: Style.space(5); radius: width / 2
                color: root.live ? root.accent : root.dim
                anchors.verticalCenter: parent.verticalCenter
              }
              Text {
                text: root.live ? "LIVE" : "STALE"
                textFormat: Text.PlainText
                color: root.live ? root.accent : root.dim
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                font.bold: true
              }
            }
          }
        }

        // ---- open the map
        Rectangle {
          width: parent.width
          height: Style.space(32)
          radius: Style.cornerRadius
          color: mapMouse.containsMouse ? root.fillFor(root.accent, 0.12) : root.fillFor(root.accent, 0.06)
          border.color: root.fillFor(root.accent, 0.4)
          opacity: root.opening ? 0.5 : 1.0
          Text {
            anchors.centerIn: parent
            text: root.opening ? "opening…" : "open the traffic map  ↗"
            textFormat: Text.PlainText; color: root.accent
            font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
          }
          MouseArea {
            id: mapMouse; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; enabled: !root.opening
            onClicked: root.openMap()
          }
        }

        // ---- restart collector + GUI
        Rectangle {
          width: parent.width
          height: Style.space(32)
          radius: Style.cornerRadius
          color: restartMouse.containsMouse && !restartProc.running ? root.fillFor(root.foreground, 0.10) : "transparent"
          border.color: root.fillFor(root.foreground, 0.22)
          opacity: restartProc.running ? 0.5 : 1.0
          Text {
            anchors.centerIn: parent
            text: restartProc.running ? "restarting…" : "restart netline"
            textFormat: Text.PlainText; color: root.dim
            font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
          }
          MouseArea {
            id: restartMouse; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; enabled: !restartProc.running
            onClicked: root.restartNetline()
          }
        }

        // ---- flagged
        PanelSectionHeader {
          text: root.flagCount > 0 ? "FLAGGED (" + root.flagCount + ")" : "FLAGGED"
          foreground: root.foreground; fontFamily: root.fontFamily
        }

        Text {
          width: parent.width
          visible: root.flagCount === 0
          text: "nothing anomalous in the last 15 minutes"
          textFormat: Text.PlainText
          color: root.dim
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          font.italic: true
        }

        Column {
          width: parent.width
          spacing: Style.space(6)
          visible: root.flagCount > 0
          Repeater {
            model: root.flagged.slice(0, 6)
            delegate: Row {
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: modelData.comm || "?"
                textFormat: Text.PlainText
                color: root.urgent
                font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
                width: Style.space(70); elide: Text.ElideRight
              }
              Text {
                text: "→ " + (modelData.where || "")
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                width: parent.width - Style.space(70) - Style.space(74) - parent.spacing * 2
                elide: Text.ElideRight
              }
              Text {
                text: modelData.pretty || ""
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                width: Style.space(58); horizontalAlignment: Text.AlignRight
              }
            }
          }
        }

        // ---- top destinations
        PanelSectionHeader {
          text: "TOP DESTINATIONS"
          foreground: root.foreground; fontFamily: root.fontFamily
        }

        Column {
          width: parent.width
          spacing: Style.space(5)
          Repeater {
            model: root.topDests
            delegate: Row {
              width: parent.width
              spacing: Style.space(8)
              Text {
                text: modelData.dest
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                width: parent.width - Style.space(64) - parent.spacing
                elide: Text.ElideRight
              }
              Text {
                text: modelData.pretty
                textFormat: Text.PlainText
                color: root.accent
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                width: Style.space(56); horizontalAlignment: Text.AlignRight
              }
            }
          }
        }


        // ---- agents: who is logged in, per lane
        PanelSectionHeader {
          text: root.agentsKnown
                ? "AGENTS · " + root.agents.filter(function(a){return a.state === "ok"}).length
                  + " of " + root.agents.length + " ready"
                : "AGENTS"
          foreground: root.foreground; fontFamily: root.fontFamily
        }

        Text {
          width: parent.width
          visible: root.agentsKnown && root.agents.length === 0
          text: "no agent CLIs found"
          textFormat: Text.PlainText; color: root.dim
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          font.italic: true
        }

        Column {
          width: parent.width
          spacing: Style.space(4)
          Repeater {
            model: root.agents
            delegate: Row {
              width: parent.width
              spacing: Style.space(8)

              // state dot: green ok, red expired/broken, dim unknown
              Rectangle {
                width: Style.space(5); height: Style.space(5); radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                color: modelData.state === "ok" ? root.accent
                     : (modelData.state === "expired" || modelData.state === "broken") ? root.urgent
                     : root.dim
              }

              Text {
                text: modelData.label + (modelData.lane === "work" ? " (work)" : "")
                textFormat: Text.PlainText
                color: modelData.state === "ok" ? root.foreground : root.dim
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                width: Style.space(112); elide: Text.ElideRight
              }

              Text {
                text: modelData.state === "ok"
                      ? (modelData.identity || "logged in")
                      : modelData.state
                textFormat: Text.PlainText
                color: modelData.state === "ok" ? root.dim : root.urgent
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                width: parent.width - Style.space(112) - Style.space(14) - parent.spacing * 2
                elide: Text.ElideRight
              }
            }
          }
        }

        Text {
          width: parent.width
          visible: root.lastError !== ""
          text: "! " + root.lastError
          textFormat: Text.PlainText
          color: root.urgent
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
