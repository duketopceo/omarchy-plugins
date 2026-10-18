import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Binary NordVPN toggle + location picker. The glyph IS the switch:
// OFF → click opens the picker (recommended + 5 US cities), picking
// connects. ON → click disconnects, all the way off. Status polls the
// CLI every 20s via bin/probe_nordvpn.py — no network polling.
Panel {
  id: root
  moduleName: "io.github.duketopceo.nordvpn"
  ipcTarget: "io.github.duketopceo.nordvpn"

  property bool statusKnown: false
  property bool busy: false             // a control verb is in flight
  property bool cliOk: true
  property bool loggedIn: true
  property string state: "disconnected" // connected|disconnected|connecting
  property var st: ({})                 // status detail map
  property bool killswitch: false
  property string lastError: ""
  property string lastAction: ""

  readonly property bool connected: state === "connected"
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property color glyphColor: !statusKnown ? dim
    : connected ? accent : state === "connecting" ? accent : dim
  readonly property string statusText: !statusKnown ? "CHECKING"
    : state === "connecting" ? "CONNECTING" : connected ? "ON" : "OFF"
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
    "LANG": null,
    "LC_ALL": "C"
  })

  function fillFor(c, alpha) {
    return Qt.rgba(c.r, c.g, c.b, alpha)
  }

  function refresh() {
    if (statusProc.running) return
    statusProc.running = true
    statusDeadline.restart()
  }

  function control(argv, label) {
    if (ctrlProc.running) return
    root.busy = true
    root.lastAction = label
    ctrlProc.command = [root.py, root.pluginRoot + "/bin/probe_nordvpn.py"].concat(argv)
    ctrlProc.running = true
    ctrlDeadline.restart()
  }

  function connectTo(target1, target2, label) {
    var argv = ["connect"]
    if (target1) argv.push(target1)
    if (target2) argv.push(target2)
    control(argv, "connect " + label)
  }

  function applyStatus(data) {
    if (!data || typeof data !== "object") return
    var wasConnected = root.connected
    root.cliOk = data.cli === true
    root.loggedIn = data.logged_in === true
    var s = data.status
    if (s && typeof s === "object") {
      root.state = typeof s.state === "string" ? s.state : "disconnected"
      root.st = s
    }
    root.killswitch = data.killswitch === true
    root.statusKnown = true
    root.lastError = (typeof data.error === "string" && data.error !== null)
                     ? data.error : ""
    // close only on the OFF→ON transition (a pick landing) — a steady ON
    // must not slam the panel every poll
    if (!wasConnected && root.connected) root.close()
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
    command: [root.py, root.pluginRoot + "/bin/probe_nordvpn.py"]
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
    id: ctrlProc
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        ctrlDeadline.stop()
        root.busy = false
        try {
          if (!text || text.trim().length === 0 || text.length > 100000) {
            root.refresh(); return
          }
          var data = JSON.parse(text)
          if (data && typeof data === "object") {
            if (data.ok === false)
              root.lastError = root.lastAction + ": " + (data.error || "failed")
            root.applyStatus(data)
          }
        } catch (e) { root.refresh() }
      }
    }
    stderr: StdioCollector { waitForEnd: true; onStreamFinished: {} }
    onExited: { ctrlDeadline.stop(); root.busy = false }
  }

  Timer { id: statusDeadline; interval: 15000; onTriggered: root.groupKill(statusProc) }
  Timer { id: ctrlDeadline;   interval: 45000; onTriggered: { root.groupKill(ctrlProc); root.busy = false } }
  Timer { id: statusTimer;    interval: 20000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refresh() }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰦝"
    tooltipText: "NordVPN · " + root.statusText
      + (root.connected && root.st.hostname ? "\n" + root.st.hostname : "")
    active: root.connected || root.state === "connecting"
    activeColor: root.accent
    foreground: root.connected ? root.accent : root.dim
    onPressed: function (b) {
      if (root.connected) root.control(["disconnect"], "disconnect")
      else root.toggle()
    }
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
              text: "󰦝"; textFormat: Text.PlainText
              color: root.connected ? root.accent : root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.iconLarge
            }
          }

          Column {
            width: parent.width - iconTile.width - statusPill.width - parent.spacing * 2
            spacing: Style.space(2)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              text: "NORDVPN"; textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily; font.pixelSize: Style.font.subtitle
              font.bold: true
            }
            Text {
              width: parent.width
              text: root.connected
                    ? (root.st.server || root.st.hostname) + " · " + root.st.ip
                    : "pick a location to connect"
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
            color: root.fillFor(root.connected ? root.accent : root.dim, 0.15)
            border.color: root.fillFor(root.connected ? root.accent : root.dim, 0.4)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              id: pillText
              anchors.centerIn: parent
              text: root.statusText
              textFormat: Text.PlainText
              color: root.connected ? root.accent : root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
              font.bold: true
            }
          }
        }

        // ---- degraded states ----
        Text {
          width: parent.width
          visible: !root.cliOk || !root.loggedIn
          text: !root.cliOk
                ? "! nordvpn cli not found — install nordvpn-bin"
                : "! not logged in — run `nordvpn login` in a terminal"
          textFormat: Text.PlainText
          color: root.urgent
          font.family: root.fontFamily; font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        // ---- connected detail ----
        Rectangle {
          width: parent.width
          visible: root.connected
          height: connCol.implicitHeight + Style.space(16)
          radius: Style.cornerRadius
          color: root.fillFor(root.foreground, 0.04)
          Column {
            id: connCol
            x: Style.space(8); y: Style.space(8)
            width: parent.width - Style.space(16)
            spacing: Style.space(3)
            Text {
              text: (root.st.hostname || "") || (root.st.server || "")
              textFormat: Text.PlainText; color: root.foreground
              font.family: root.fontFamily; font.pixelSize: Style.font.body; font.bold: true
            }
            Text {
              text: (root.st.city ? root.st.city + ", " : "") + (root.st.country || "")
                + "  ·  " + (root.st.ip || "") + "  ·  " + (root.st.protocol || root.st.technology || "")
              textFormat: Text.PlainText; color: root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
            }
            Text {
              visible: !!root.st.uptime
              text: "uptime " + (root.st.uptime || "")
              textFormat: Text.PlainText; color: root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
            }
            Text {
              visible: !!root.st.transfer
              text: "⇅ " + (root.st.transfer || "")
              textFormat: Text.PlainText; color: root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
            }
          }
        }

        // ---- picker ----
        PanelSectionHeader {
          visible: !root.connected
          text: "LOCATION · US"
          foreground: root.foreground; fontFamily: root.fontFamily
        }

        Rectangle {
          width: parent.width
          visible: !root.connected
          height: Style.space(30)
          radius: Style.cornerRadius
          color: quickMouse.containsMouse ? root.fillFor(root.accent, 0.10) : root.fillFor(root.accent, 0.05)
          border.color: root.fillFor(root.accent, 0.35)
          opacity: root.busy ? 0.5 : 1.0
          Text {
            anchors.centerIn: parent
            text: root.busy && root.lastAction.indexOf("connect") === 0 ? "connecting…" : "⚡ recommended"
            textFormat: Text.PlainText; color: root.accent
            font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
          }
          MouseArea {
            id: quickMouse; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; enabled: !root.busy
            onClicked: root.connectTo("", "", "recommended")
          }
        }

        Column {
          width: parent.width
          visible: !root.connected
          spacing: Style.space(2)

          Repeater {
            model: [
              { "label": "New York",     "city": "New York" },
              { "label": "Chicago",      "city": "Chicago" },
              { "label": "Dallas",       "city": "Dallas" },
              { "label": "Los Angeles",  "city": "Los Angeles" },
              { "label": "Denver",       "city": "Denver" }
            ]
            delegate: Rectangle {
              width: parent.width; height: Style.space(30)
              radius: Style.cornerRadius
              color: locMouse.containsMouse ? root.fillFor(root.accent, 0.10) : root.fillFor(root.foreground, 0.04)
              opacity: root.busy ? 0.5 : 1.0
              Row {
                anchors.fill: parent
                anchors.leftMargin: Style.space(10)
                spacing: Style.space(8)
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: "US"
                  textFormat: Text.PlainText; color: root.dim
                  font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
                }
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: modelData.label
                  textFormat: Text.PlainText; color: root.foreground
                  font.family: root.fontFamily; font.pixelSize: Style.font.body
                }
              }
              MouseArea {
                id: locMouse; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor; enabled: !root.busy
                onClicked: root.connectTo("United_States", modelData.city, "US · " + modelData.label)
              }
            }
          }
        }

        // ---- killswitch ----
        Row {
          width: parent.width
          spacing: Style.space(10)
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: "Kill switch"
            textFormat: Text.PlainText; color: root.foreground
            font.family: root.fontFamily; font.pixelSize: Style.font.body
            width: parent.width - ksPill.width - parent.spacing
          }
          Rectangle {
            id: ksPill
            height: Style.space(24)
            width: ksText.implicitWidth + Style.space(16)
            radius: height / 2
            color: root.killswitch ? root.fillFor(root.accent, 0.18) : root.fillFor(root.foreground, 0.06)
            border.color: root.killswitch ? root.fillFor(root.accent, 0.5) : root.fillFor(root.foreground, 0.15)
            opacity: root.busy ? 0.5 : 1.0
            Text {
              id: ksText; anchors.centerIn: parent
              text: root.killswitch ? "ON" : "OFF"
              textFormat: Text.PlainText
              color: root.killswitch ? root.accent : root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
            }
            MouseArea {
              anchors.fill: parent; hoverEnabled: true
              cursorShape: Qt.PointingHandCursor; enabled: !root.busy
              onClicked: root.control(["killswitch", root.killswitch ? "off" : "on"], "killswitch")
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
