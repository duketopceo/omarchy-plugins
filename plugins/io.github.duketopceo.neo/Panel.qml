import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Bar glyph + control panel for the local BrowserOS neo sidecar —
// browserclaw-{chromium,shim,server} systemd user units. Polls
// bin/probe_neo.py (stat + bounded MCP initialize) every 30s; the bar icon
// tints urgent while any unit is down or MCP won't answer.
Panel {
  id: root
  moduleName: "io.github.duketopceo.neo"
  ipcTarget: "io.github.duketopceo.neo"

  property bool statusKnown: false
  property bool busy: false           // a control verb is in flight
  property var units: ({})
  property var ports: ({})
  property bool mcpUp: false
  property string mcpName: ""
  property string mcpVersion: ""
  property int tabs: -1               // -1 = unknown (shim down/unprobed)
  property string endpoint: "http://127.0.0.1:9211/mcp"
  property string lastError: ""
  property string lastAction: ""

  readonly property int unitCount: 3
  readonly property int unitsUp: (units.chromium && units.chromium.active ? 1 : 0)
    + (units.shim && units.shim.active ? 1 : 0)
    + (units.server && units.server.active ? 1 : 0)
  readonly property bool allUp: unitsUp === unitCount
  readonly property string statusText: !statusKnown ? "CHECKING"
    : allUp && mcpUp ? "RUNNING" : unitsUp === 0 ? "DOWN" : "DEGRADED"
  readonly property color statusColor: !statusKnown ? dim
    : allUp && mcpUp ? accent : unitsUp === 0 ? urgent : urgent

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }
  readonly property string py: "/usr/bin/python3"
  readonly property var procEnv: ({
    "PATH": "/usr/bin:/bin",
    "HOME": null,
    "XDG_RUNTIME_DIR": null,
    "DBUS_SESSION_BUS_ADDRESS": null,
    "LANG": null,
    "LC_ALL": "C"
  })

  function _rgb(c) {
    if (typeof c === "string") {
      var h = c.charAt(0) === "#" ? c.substring(1) : c
      if (h.length === 8) h = h.substring(0, 6)
      if (h.length === 3)
        h = h.charAt(0) + h.charAt(0) + h.charAt(1) + h.charAt(1) + h.charAt(2) + h.charAt(2)
      return [parseInt(h.substring(0, 2), 16) / 255,
              parseInt(h.substring(2, 4), 16) / 255,
              parseInt(h.substring(4, 6), 16) / 255]
    }
    return [c.r, c.g, c.b]
  }
  function fillFor(c, alpha) {
    var rgb = _rgb(c)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

  function refresh() {
    if (statusProc.running) return
    statusProc.command = [root.py, root.pluginRoot + "/bin/probe_neo.py"]
    statusProc.running = true
    statusDeadline.restart()
  }

  function control(verb, unit) {
    if (ctrlProc.running || verb === "") return
    root.busy = true
    root.lastAction = unit ? verb + " " + unit : verb
    ctrlProc.command = unit
      ? [root.py, root.pluginRoot + "/bin/probe_neo.py", verb, unit]
      : [root.py, root.pluginRoot + "/bin/probe_neo.py", verb]
    ctrlProc.running = true
    ctrlDeadline.restart()
  }

  function applyStatus(data) {
    if (!data || typeof data !== "object") return
    var u = data.units
    if (u && typeof u === "object" && !Array.isArray(u)) root.units = u
    var p = data.ports
    if (p && typeof p === "object" && !Array.isArray(p)) root.ports = p
    var m = data.mcp
    if (m && typeof m === "object") {
      root.mcpUp = m.up === true
      root.mcpName = typeof m.server === "string" ? m.server : ""
      root.mcpVersion = typeof m.version === "string" ? m.version : ""
    }
    if (typeof data.endpoint === "string" && data.endpoint !== "")
      root.endpoint = data.endpoint
    root.tabs = (typeof data.tabs === "number" && data.tabs >= 0)
                ? Math.floor(data.tabs) : -1
    root.statusKnown = true
    root.lastError = typeof data.error === "string" && data.error !== null
                     ? data.error : ""
  }

  function groupKill(proc) {
    if (proc.running) {
      var pid = proc.pid
      if (pid > 0)
        Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
      proc.signal(9)
    }
  }

  onOpenedChanged: if (opened) root.refresh()

  Process {
    id: statusProc
    command: [root.py, root.pluginRoot + "/bin/probe_neo.py"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        statusDeadline.stop()
        try {
          if (!text || text.trim().length === 0) return
          if (text.length > 100000) return
          root.applyStatus(JSON.parse(text))
        } catch (e) {}
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("probe_neo status stderr: " + err.substring(0, 500))
      }
    }
    onExited: statusDeadline.stop()
  }

  // Status worst case is the 3s MCP timeout + one systemctl show — 12s is
  // generous; control verbs can sit through a unit's TimeoutStopSec (15s) so
  // the control deadline clears the helper's own 45s backstop.
  Timer { id: statusDeadline; interval: 15000; onTriggered: root.groupKill(statusProc) }
  Timer { id: statusTimer; interval: 30000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refresh() }

  Process {
    id: ctrlProc
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        ctrlDeadline.stop()
        root.busy = false
        try {
          if (!text || text.trim().length === 0) { root.refresh(); return }
          if (text.length > 100000) return
          var data = JSON.parse(text)
          if (data === null || typeof data !== "object") { root.refresh(); return }
          if (data.status && typeof data.status === "object")
            root.applyStatus(data.status)
          if (typeof data.error === "string" && data.error !== null)
            root.lastError = root.lastAction + ": " + data.error
        } catch (e) { root.refresh() }
      }
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("probe_neo " + root.lastAction + " stderr: " + err.substring(0, 500))
      }
    }
    onExited: { ctrlDeadline.stop(); root.busy = false }
  }

  Timer { id: ctrlDeadline; interval: 55000; onTriggered: { root.groupKill(ctrlProc); root.busy = false } }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰖟"
    tooltipText: "BrowserOS neo · " + root.statusText
    active: root.statusKnown && !(root.allUp && root.mcpUp)
    activeColor: root.urgent
    onPressed: function (b) { root.refresh(); root.toggle() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(380), 420)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 560)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()

      Column {
        id: mainColumn
        width: parent.width
        spacing: Style.space(10)

        // ---- header ----
        Row {
          width: parent.width
          spacing: Style.space(10)

          Rectangle {
            id: iconTile
            width: Style.space(34); height: Style.space(34)
            radius: Style.cornerRadius
            color: root.fillFor(root.accent, 0.12)
            anchors.verticalCenter: parent.verticalCenter

            Text {
              anchors.centerIn: parent
              text: "󰖟"; textFormat: Text.PlainText
              color: root.accent
              font.family: root.fontFamily; font.pixelSize: Style.font.iconLarge
            }
          }

          Column {
            width: parent.width - iconTile.width - statusPill.width - parent.spacing * 2
            spacing: Style.space(2)
            anchors.verticalCenter: parent.verticalCenter

            Text {
              text: "BrowserOS neo"; textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily; font.pixelSize: Style.font.subtitle
              font.bold: true
            }
            Text {
              width: parent.width
              text: "agent browser sidecar · claw-server + shim + headless chromium"
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }

          Rectangle {
            id: statusPill
            height: Style.space(22)
            width: pillText.implicitWidth + Style.space(16)
            radius: height / 2
            color: root.fillFor(root.statusColor, 0.15)
            border.color: root.fillFor(root.statusColor, 0.4)
            anchors.verticalCenter: parent.verticalCenter

            Text {
              id: pillText
              anchors.centerIn: parent
              text: root.statusText
              textFormat: Text.PlainText
              color: root.statusColor
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
              font.bold: true
            }
          }
        }

        // ---- units ----
        PanelSectionHeader { text: "SERVICES"; foreground: root.foreground; fontFamily: root.fontFamily }

        Repeater {
          model: [
            { "key": "chromium", "label": "chromium", "hint": "CDP :49337", "port": "49337" },
            { "key": "shim", "label": "cdp shim", "hint": ":49338", "port": "49338" },
            { "key": "server", "label": "claw-server", "hint": "MCP :9211", "port": "9211" }
          ]

          delegate: Rectangle {
            width: parent.width
            height: Style.space(30)
            radius: Style.cornerRadius
            color: root.fillFor(root.foreground, 0.04)
            border.color: root.fillFor(root.foreground, 0.08)

            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: Style.space(10)
              anchors.rightMargin: Style.space(10)
              spacing: Style.space(8)

              Rectangle {
                width: Style.space(8); height: Style.space(8)
                radius: width / 2
                color: (root.units[modelData.key] && root.units[modelData.key].active)
                       ? root.accent : root.urgent
              }
              Text {
                text: modelData.label
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall
                font.bold: true
              }
              Text {
                Layout.fillWidth: true
                text: (root.units[modelData.key] ? String(root.units[modelData.key].sub || "?") : "?")
                      + " · " + modelData.hint
                      + (root.ports[modelData.port] === false ? " (not bound)" : "")
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
              Text {
                text: root.units[modelData.key] && root.units[modelData.key].pid
                      ? "pid " + root.units[modelData.key].pid : ""
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
              }
              // Per-unit restart — probes the single named unit server-side.
              Rectangle {
                height: Style.space(18)
                width: unitRstText.implicitWidth + Style.space(10)
                radius: height / 2
                color: mUnitRst.containsMouse ? root.fillFor(root.accent, 0.15) : "transparent"
                border.color: root.fillFor(root.accent, 0.45)
                Layout.alignment: Qt.AlignVCenter

                Text {
                  id: unitRstText
                  anchors.centerIn: parent
                  text: "restart"
                  textFormat: Text.PlainText
                  color: root.foreground
                  font.family: root.fontFamily; font.pixelSize: Style.font.caption
                }
                MouseArea {
                  id: mUnitRst
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.control("restart", modelData.key)
                }
              }
            }
          }
        }

        // Live browser state — tab count via the shim's /json/list.
        Text {
          width: parent.width
          text: "open tabs: " + (root.tabs >= 0 ? String(root.tabs) : "—")
          textFormat: Text.PlainText
          color: root.dim
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }

        // ---- endpoint ----
        PanelSectionHeader { text: "AGENT ENDPOINT"; foreground: root.foreground; fontFamily: root.fontFamily }

        Rectangle {
          width: parent.width
          height: epRow.implicitHeight + Style.space(14)
          radius: Style.cornerRadius
          color: root.fillFor(root.foreground, 0.04)
          border.color: root.fillFor(root.foreground, 0.08)

          RowLayout {
            id: epRow
            width: parent.width - Style.space(20)
            anchors.centerIn: parent
            spacing: Style.space(8)

            Column {
              Layout.fillWidth: true
              spacing: Style.space(2)
              Text {
                width: parent.width
                text: root.endpoint
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
              Text {
                width: parent.width
                text: root.mcpUp
                      ? "mcp answers — " + root.mcpName + " " + root.mcpVersion
                      : "mcp not answering"
                textFormat: Text.PlainText
                color: root.mcpUp ? root.dim : root.urgent
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }

            Rectangle {
              height: Style.space(22)
              width: copyText.implicitWidth + Style.space(12)
              radius: Style.cornerRadius
              color: mCopy.containsMouse ? root.fillFor(root.accent, 0.12) : "transparent"
              border.color: root.fillFor(root.accent, 0.5)
              anchors.verticalCenter: parent.verticalCenter

              Text {
                id: copyText
                anchors.centerIn: parent
                text: "copy"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
              }
              MouseArea {
                id: mCopy
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: Quickshell.execDetached(
                  ["/usr/bin/wl-copy", "--", root.endpoint])
              }
            }
          }
        }

        // ---- controls ----
        PanelSectionHeader { text: "CONTROL"; foreground: root.foreground; fontFamily: root.fontFamily }

        Row {
          width: parent.width
          spacing: Style.space(8)

          Repeater {
            model: [
              { "verb": "start", "label": "Start" },
              { "verb": "restart", "label": "Restart" },
              { "verb": "stop", "label": "Stop" }
            ]

            delegate: Rectangle {
              height: Style.space(26)
              width: ctlText.implicitWidth + Style.space(18)
              radius: Style.cornerRadius
              color: (mCtl.containsMouse && !root.busy)
                     ? root.fillFor(root.accent, 0.12) : "transparent"
              border.color: root.fillFor(
                modelData.verb === "stop" ? root.urgent : root.accent, 0.5)
              opacity: root.busy ? 0.5 : 1.0

              Text {
                id: ctlText
                anchors.centerIn: parent
                text: (root.busy && root.lastAction === modelData.verb)
                      ? modelData.label + "…" : modelData.label
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily; font.pixelSize: Style.font.caption
              }
              MouseArea {
                id: mCtl
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                enabled: !root.busy
                onClicked: root.control(modelData.verb)
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

        Text {
          width: parent.width
          text: "agents reach it via MCP; the cockpit opens in the sidecar profile's newtab · docs: ~/.local/share/browserclaw/SETUP.md"
          textFormat: Text.PlainText
          color: root.dim
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
