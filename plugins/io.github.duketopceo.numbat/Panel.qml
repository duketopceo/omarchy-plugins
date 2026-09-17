import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.duketopceo.numbat"
  ipcTarget: "io.github.duketopceo.numbat"

  property bool probed: false
  property bool installed: false
  property bool hooksSeen: false
  property int findingsCount: 0
  property var findings: []
  property var activeAgents: []
  property string recordsPath: ""
  property string probeError: ""
  property bool isRefreshing: false

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property color muted: Color.muted
  readonly property color cardBg: Qt.rgba(fg.r, fg.g, fg.b, 0.04)
  readonly property color cardBorder: Qt.rgba(fg.r, fg.g, fg.b, 0.08)
  // Setup state exists only once a probe answer has landed — the button must
  // not flash "not installed" on machines that have numbat before first poll.
  readonly property bool needsSetup: probed && (!installed || !hooksSeen)
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }

  // Absolute interpreter + minimal env: a PATH-preceding shadow "python3"
  // must never run inside this long-lived shell process.
  readonly property string py: "/usr/bin/python3"
  readonly property var procEnv: ({
    "PATH": "/usr/bin:/bin",
    "HOME": null,
    "XDG_RUNTIME_DIR": null,
    "LANG": null,
    "LC_ALL": "C"
  })

  function refresh() {
    if (statusProc.running) return
    isRefreshing = true
    statusProc.running = true
    statusDeadline.restart()
  }

  // probe_numbat.py emits ISO-8601 "Z" timestamps; V4's Date parses them
  // directly. Unparseable/absent input collapses to "—" instead of "NaNh ago".
  function relTime(iso) {
    if (!iso) return "—"
    var ms = new Date(String(iso)).getTime()
    if (!isFinite(ms)) return "—"
    var m = Math.floor(Math.max(0, Date.now() - ms) / 60000)
    if (m < 1) return "just now"
    var h = Math.floor(m / 60)
    var d = Math.floor(h / 24)
    if (d > 0) return d + "d " + (h % 24) + "h ago"
    if (h > 0) return h + "h " + (m % 60) + "m ago"
    return m + "m ago"
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onOpenedChanged: if (opened) root.refresh()

  Process {
    id: statusProc
    command: [root.py, root.pluginRoot + "/bin/probe_numbat.py"]
    clearEnvironment: true
    environment: root.procEnv
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        statusDeadline.stop()
        root.isRefreshing = false
        try {
          if (!text || text.trim().length === 0) return
          if (text.length > 300000) return
          var data = JSON.parse(text)
          if (typeof data !== "object" || data === null) return
          root.probed = true
          root.installed = data.installed === true
          root.hooksSeen = data.hooks_seen === true
          root.findingsCount = Math.max(0, Number(data.findings_24h) || 0)
          root.findings = (Array.isArray(data.findings) ? data.findings : []).slice(0, 20)
          root.activeAgents = (Array.isArray(data.active_agents) ? data.active_agents : []).slice(0, 10)
          root.recordsPath = typeof data.records_path === "string" ? data.records_path : ""
          root.probeError = typeof data.error === "string" ? data.error : ""
        } catch (e) {}
      }
    }
    onExited: {
      statusDeadline.stop()
      root.isRefreshing = false
    }
  }
  // Hard whole-job deadline: a stuck probe is killed and reaped, never left
  // running past one refresh interval. probe_numbat.py calls os.setsid() and
  // keeps helpers in its own session group, so a group-kill reaches the whole
  // tree even if Python is stuck inside a helper wait.
  Timer {
    id: statusDeadline
    interval: 10000
    onTriggered: {
      if (statusProc.running) {
        var pid = statusProc.pid
        if (pid > 0)
          Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
        statusProc.signal(9)
        root.isRefreshing = false
      }
    }
  }

  Timer {
    id: refreshTimer
    interval: 15000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰐷"
    tooltipText: !root.probed ? "Numbat · Agent Activity"
      : !root.installed ? "Numbat · Agent Activity · not installed"
      : !root.hooksSeen ? "Numbat · Agent Activity · hooks not installed"
      : "Numbat · Agent Activity · " + root.findingsCount + " finding"
        + (root.findingsCount === 1 ? "" : "s") + " / 24h"
    dimmed: root.needsSetup
    active: root.hooksSeen
    activeColor: root.findingsCount > 0 ? root.urgent : root.accent
    onPressed: function (b) { root.refresh(); root.toggle() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(400), 460)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 720)

    Column {
      id: mainColumn
      width: parent.width
      spacing: Style.space(12)

      // Header card: title + findings-24h pill + active-agent count.
      Rectangle {
        width: parent.width
        height: 64
        radius: 10
        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.08)
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.25)
        border.width: 1

        RowLayout {
          anchors.fill: parent
          anchors.leftMargin: 16
          anchors.rightMargin: 16
          spacing: 12

          Rectangle {
            width: 36
            height: 36
            radius: 8
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.2)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "󰐷"
              color: root.hooksSeen ? root.accent : root.muted
              font.pixelSize: 20
            }
          }

          Column {
            Layout.fillWidth: true
            spacing: 2
            Text {
              textFormat: Text.PlainText
              text: "AGENT ACTIVITY RADAR"
              color: root.fg
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
            }
            Text {
              width: parent.width
              text: root.probeError !== "" ? root.probeError
                : (root.hooksSeen && root.recordsPath !== ""
                  ? "Watching " + root.recordsPath
                  : "Hook-driven agent activity monitor")
              textFormat: Text.PlainText
              color: root.muted
              font.pixelSize: 10
              elide: Text.ElideMiddle
            }
          }

          Column {
            visible: root.hooksSeen
            spacing: 4
            Rectangle {
              height: 22
              width: 84
              radius: 11
              color: root.findingsCount > 0
                ? Qt.rgba(root.urgent.r, root.urgent.g, root.urgent.b, 0.2)
                : Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.15)
              Text {
                anchors.centerIn: parent
                text: root.findingsCount + " / 24H"
                textFormat: Text.PlainText
                color: root.findingsCount > 0 ? root.urgent : root.accent
                font.pixelSize: 9
                font.bold: true
              }
            }
            Text {
              anchors.horizontalCenter: parent.horizontalCenter
              text: root.activeAgents.length + " agent" + (root.activeAgents.length === 1 ? "" : "s") + " active"
              textFormat: Text.PlainText
              color: root.muted
              font.pixelSize: 9
            }
          }

          Rectangle {
            visible: root.needsSetup
            height: 22
            width: 62
            radius: 11
            color: Qt.rgba(root.muted.r, root.muted.g, root.muted.b, 0.15)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "SETUP"
              color: root.muted
              font.pixelSize: 9
              font.bold: true
            }
          }
        }
      }

      // Setup pane — replaces the lists until numbat is installed and its
      // hooks have produced records.
      Rectangle {
        visible: root.needsSetup
        width: parent.width
        height: setupColumn.implicitHeight + 24
        radius: 10
        color: root.cardBg
        border.color: root.cardBorder
        border.width: 1

        Column {
          id: setupColumn
          anchors.fill: parent
          anchors.margins: 12
          spacing: 8

          Text {
            text: root.installed ? "HOOKS NOT INSTALLED" : "NUMBAT NOT INSTALLED"
            textFormat: Text.PlainText
            color: root.fg
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }
          Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: root.installed
              ? "numbat is installed, but no hook events have been recorded yet. Install the hooks once and agent activity shows up here automatically."
              : "numbat watches coding-agent hooks and records what they do. Install the numbat CLI to switch this radar on."
            textFormat: Text.PlainText
            color: root.muted
            font.pixelSize: 10
          }
          // A user instruction, not a live command — PlainText, never exec'd.
          Rectangle {
            visible: root.installed && !root.hooksSeen
            width: parent.width
            height: 30
            radius: 6
            color: Qt.rgba(root.muted.r, root.muted.g, root.muted.b, 0.1)
            border.color: root.cardBorder
            border.width: 1
            Text {
              anchors.centerIn: parent
              text: "Run: numbat hook install --agent all"
              textFormat: Text.PlainText
              color: root.fg
              font.pixelSize: 10
              font.bold: true
            }
          }
        }
      }

      // Scrollable findings + agents area.
      Flickable {
        visible: root.hooksSeen
        width: parent.width
        height: Math.min(440, contentColumn.implicitHeight)
        contentWidth: width
        contentHeight: contentColumn.implicitHeight
        clip: true
        Column {
          id: contentColumn
          width: parent.width
          spacing: Style.space(10)
          Column {
            width: parent.width
            spacing: 6
            Text {
              textFormat: Text.PlainText
              text: "FINDINGS (24H)"
              color: root.muted
              font.pixelSize: 10
              font.bold: true
            }
            Text {
              textFormat: Text.PlainText
              visible: root.findings.length === 0
              text: "No findings in the last 24h"
              color: root.muted
              font.pixelSize: 10
            }
            Repeater {
              model: root.findings
              delegate: Rectangle {
                width: parent.width
                height: 44
                radius: 8
                color: root.cardBg
                border.color: root.cardBorder
                border.width: 1
                RowLayout {
                  anchors.fill: parent
                  anchors.leftMargin: 12
                  anchors.rightMargin: 12
                  spacing: 10
                  Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: root.accent
                  }
                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      width: parent.width
                      text: modelData.rule || "unnamed rule"
                      textFormat: Text.PlainText
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                      elide: Text.ElideRight
                    }
                    Text {
                      width: parent.width
                      text: (modelData.agent || "unknown agent") + " · " + root.relTime(modelData.observed_at)
                      textFormat: Text.PlainText
                      color: root.muted
                      font.pixelSize: 10
                      elide: Text.ElideRight
                    }
                  }
                }
              }
            }
          }
          Column {
            width: parent.width
            spacing: 6
            Text {
              textFormat: Text.PlainText
              text: "ACTIVE AGENTS"
              color: root.muted
              font.pixelSize: 10
              font.bold: true
            }
            Text {
              textFormat: Text.PlainText
              visible: root.activeAgents.length === 0
              text: "No agent activity recorded"
              color: root.muted
              font.pixelSize: 10
            }
            Repeater {
              model: root.activeAgents
              delegate: Rectangle {
                width: parent.width
                height: 40
                radius: 8
                color: root.cardBg
                border.color: root.cardBorder
                border.width: 1
                RowLayout {
                  anchors.fill: parent
                  anchors.leftMargin: 12
                  anchors.rightMargin: 12
                  spacing: 10
                  Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: root.accent
                  }
                  Text {
                    Layout.fillWidth: true
                    text: modelData.name || "unnamed agent"
                    textFormat: Text.PlainText
                    color: root.fg
                    font.pixelSize: Style.font.bodySmall
                    font.bold: true
                    elide: Text.ElideRight
                  }
                  Text {
                    text: root.relTime(modelData.last_event)
                    textFormat: Text.PlainText
                    color: root.muted
                    font.pixelSize: 10
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
