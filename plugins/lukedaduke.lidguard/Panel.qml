import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Timed lid-close stay-awake. The glyph IS the status: dim = lid close
// suspends normally, accent = a handle-lid-switch inhibitor is armed and
// agents keep running with the lid shut. Click opens the duration picker.
// All state lives in bin/lidguard.py — systemd-run transient user unit
// holding the inhibitor, expiry tracked in ~/.local/state/lidguard/.
Panel {
  id: root
  moduleName: "lukedaduke.lidguard"
  ipcTarget: "lukedaduke.lidguard"

  property bool statusKnown: false
  property bool busy: false
  property bool armed: false
  property var remainingS: null        // seconds, -1 = indefinite, null = unknown
  property var expiresAt: null         // epoch, null when indefinite/unknown
  property string lastError: ""
  property string lastAction: ""

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property color glyphColor: !statusKnown ? dim : armed ? accent : dim
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
    "LANG": "C",
    "LC_ALL": "C"
  })

  function fillFor(c, alpha) {
    return Qt.rgba(c.r, c.g, c.b, alpha)
  }

  function fmtRemaining() {
    if (!armed) return "off"
    if (remainingS === -1) return "until disarmed"
    if (remainingS === null || remainingS === undefined) return "armed"
    var s = Math.max(0, remainingS)
    var h = Math.floor(s / 3600)
    var m = Math.floor((s % 3600) / 60)
    if (h > 0) return h + "h" + (m > 0 ? m + "m" : "")
    return m + "m"
  }

  function fmtExpiry() {
    if (!armed) return "lid close suspends normally"
    if (expiresAt) {
      var d = new Date(expiresAt * 1000)
      var hh = d.getHours().toString().padStart(2, "0")
      var mm = d.getMinutes().toString().padStart(2, "0")
      return "lid-close suspend blocked until " + hh + ":" + mm
    }
    return "lid-close suspend blocked " + fmtRemaining()
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
    ctrlProc.command = [root.py, root.pluginRoot + "/bin/lidguard.py"].concat(argv)
    ctrlProc.running = true
    ctrlDeadline.restart()
  }

  function arm(secs, label) {
    control(["arm", secs.toString()], label)
  }

  function applyStatus(data) {
    if (!data || typeof data !== "object") return
    root.armed = data.armed === true
    root.remainingS = (typeof data.remaining_s === "number") ? data.remaining_s : null
    root.expiresAt = (typeof data.expires_at === "number") ? data.expires_at : null
    root.statusKnown = true
    root.lastError = (typeof data.error === "string" && data.error !== null)
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
    command: [root.py, root.pluginRoot + "/bin/lidguard.py", "status"]
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
            else
              root.close()
            root.applyStatus(data)
          }
        } catch (e) { root.refresh() }
      }
    }
    stderr: StdioCollector { waitForEnd: true; onStreamFinished: {} }
    onExited: { ctrlDeadline.stop(); root.busy = false }
  }

  Timer { id: statusDeadline; interval: 15000; onTriggered: root.groupKill(statusProc) }
  Timer { id: ctrlDeadline;   interval: 15000; onTriggered: { root.groupKill(ctrlProc); root.busy = false } }
  Timer { id: statusTimer;    interval: 30000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refresh() }
  // 1s ticker so the remaining-time text counts down between polls
  Timer { id: tickTimer;      interval: 1000;  running: root.armed && root.remainingS !== null && root.remainingS > 0; repeat: true; onTriggered: { root.remainingS = Math.max(0, root.remainingS - 1) } }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰐥"
    tooltipText: "Lid Guard · " + (root.armed ? fmtRemaining() + " left" : "off")
    active: root.armed
    activeColor: root.accent
    foreground: root.glyphColor
    onPressed: function (b) { root.toggle() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(340), 380)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 320)

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
              text: "󰐥"; textFormat: Text.PlainText
              color: root.glyphColor
              font.family: root.fontFamily; font.pixelSize: Style.font.iconLarge
            }
          }

          Column {
            width: parent.width - iconTile.width - statusPill.width - parent.spacing * 2
            spacing: Style.space(2)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              text: "LID GUARD"; textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily; font.pixelSize: Style.font.subtitle
              font.bold: true
            }
            Text {
              width: parent.width
              text: root.fmtExpiry()
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
            color: root.fillFor(root.armed ? root.accent : root.dim, 0.15)
            border.color: root.fillFor(root.armed ? root.accent : root.dim, 0.4)
            anchors.verticalCenter: parent.verticalCenter
            Text {
              id: pillText
              anchors.centerIn: parent
              text: root.armed ? "ARMED" : "OFF"
              textFormat: Text.PlainText
              color: root.armed ? root.accent : root.dim
              font.family: root.fontFamily; font.pixelSize: Style.font.caption
              font.bold: true
            }
          }
        }

        // ---- duration picker ----
        PanelSectionHeader {
          text: "KEEP RUNNING WITH LID CLOSED"
          foreground: root.foreground; fontFamily: root.fontFamily
        }

        Row {
          width: parent.width
          spacing: Style.space(6)

          Repeater {
            model: [
              { "label": "1h",  "secs": 3600 },
              { "label": "2h",  "secs": 7200 },
              { "label": "4h",  "secs": 14400 },
              { "label": "8h",  "secs": 28800 },
              { "label": "∞",   "secs": "inf" }
            ]
            delegate: Rectangle {
              width: (parent.width - parent.spacing * 4) / 5
              height: Style.space(30)
              radius: Style.cornerRadius
              color: durMouse.containsMouse ? root.fillFor(root.accent, 0.10) : root.fillFor(root.accent, 0.05)
              border.color: root.fillFor(root.accent, 0.35)
              opacity: root.busy ? 0.5 : 1.0
              Text {
                anchors.centerIn: parent
                text: root.busy && root.lastAction === "arm " + modelData.label
                      ? "…" : modelData.label
                textFormat: Text.PlainText; color: root.accent
                font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
              }
              MouseArea {
                id: durMouse; anchors.fill: parent; hoverEnabled: true
                cursorShape: Qt.PointingHandCursor; enabled: !root.busy
                onClicked: root.arm(modelData.secs, "arm " + modelData.label)
              }
            }
          }
        }

        // ---- disarm ----
        Rectangle {
          width: parent.width
          visible: root.armed
          height: Style.space(30)
          radius: Style.cornerRadius
          color: offMouse.containsMouse ? root.fillFor(root.urgent, 0.10) : root.fillFor(root.foreground, 0.04)
          border.color: root.fillFor(root.urgent, 0.3)
          opacity: root.busy ? 0.5 : 1.0
          Text {
            anchors.centerIn: parent
            text: root.busy && root.lastAction === "disarm" ? "disarming…" : "disarm — normal lid behavior"
            textFormat: Text.PlainText; color: root.urgent
            font.family: root.fontFamily; font.pixelSize: Style.font.caption; font.bold: true
          }
          MouseArea {
            id: offMouse; anchors.fill: parent; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; enabled: !root.busy
            onClicked: root.control(["disarm"], "disarm")
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
