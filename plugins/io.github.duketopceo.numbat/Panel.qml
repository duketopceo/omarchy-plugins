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
  property var events: []
  property string recordsPath: ""
  property string probeError: ""
  property bool isRefreshing: false
  property string currentTab: "activity" // "activity" | "findings" | "log"

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color accent: Color.accent
  readonly property color urgent: (Color.urgent === undefined || Color.urgent === null) ? foreground : Color.urgent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  // Setup state exists only once a probe answer has landed — the banner must
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

  // _rgb / accentFill / fgFill — same helpers dayflow uses so every tint in
  // this panel is derived from theme colors, never a hardcoded hex.
  function _rgb(c) {
    if (typeof c === "string") {
      var h = c.charAt(0) === "#" ? c.substring(1) : c
      if (h.length === 8) h = h.substring(0, 6)
      if (h.length === 3)
        h = h.charAt(0) + h.charAt(0) + h.charAt(1) + h.charAt(1) + h.charAt(2) + h.charAt(2)
      if (h.length === 6) {
        return [parseInt(h.substring(0, 2), 16) / 255,
                parseInt(h.substring(2, 4), 16) / 255,
                parseInt(h.substring(4, 6), 16) / 255]
      }
      return [1, 1, 1]
    }
    if (c === undefined || c === null) return [1, 1, 1]
    return [c.r, c.g, c.b]
  }

  function accentFill(alpha) {
    var rgb = _rgb(accent)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

  function urgentFill(alpha) {
    var rgb = _rgb(urgent)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

  function fgFill(alpha) {
    var rgb = _rgb(foreground)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
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

  // Findings carry severity only when the source record had the field; any
  // meaningful level highlights the row's left border, absent/low -> uniform.
  function severe(f) {
    if (!f) return false
    var s = String(f.severity === undefined || f.severity === null ? "" : f.severity).toLowerCase()
    if (s === "") return false
    return !(s === "info" || s === "low" || s === "none" || s === "debug")
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
          root.events = (Array.isArray(data.events) ? data.events : []).slice(0, 30)
          root.recordsPath = typeof data.records_path === "string" ? data.records_path : ""
          root.probeError = typeof data.error === "string" && data.error !== null ? data.error : ""
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
  // keeps helpers in its own session group (JOB_DEADLINE_S = 8s inside), so a
  // group-kill reaches the whole tree even if Python is stuck in a wait.
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
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(500))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(640))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) { if (t === "r" || t === "R") root.refresh() }

      Column {
        id: content
        width: parent.width
        leftPadding: Style.space(12)
        rightPadding: Style.space(12)
        topPadding: Style.space(12)
        bottomPadding: Style.space(12)
        spacing: Style.space(10)

        // ---- header ----
        Row {
          width: parent.width - content.leftPadding - content.rightPadding
          spacing: Style.space(10)

          // Radar glyph tile
          Rectangle {
            width: Style.space(36)
            height: Style.space(36)
            radius: Style.cornerRadius
            anchors.verticalCenter: parent.verticalCenter
            color: root.accentFill(0.15)
            border.color: root.accentFill(0.30)

            Text {
              anchors.centerIn: parent
              text: "󰐷"
              textFormat: Text.PlainText
              color: root.hooksSeen ? root.accent : root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.iconLarge
            }
          }

          Column {
            width: parent.width - Style.space(36) - statusPill.width - parent.spacing * 2
            spacing: Style.space(2)
            anchors.verticalCenter: parent.verticalCenter

            Row {
              spacing: Style.space(6)

              Rectangle {
                width: Style.space(7)
                height: Style.space(7)
                radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                color: root.findingsCount > 0 ? root.urgent
                  : root.hooksSeen ? root.accent : root.dim
              }

              Text {
                text: "Numbat"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.subtitle
                font.bold: true
              }
            }

            Text {
              width: parent.width
              text: "ai-agent activity radar"
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }

          // Status pill — FINDINGS (urgent) > LIVE (accent) > SETUP (dim)
          Rectangle {
            id: statusPill
            height: Style.space(28)
            width: statusText.implicitWidth + Style.space(16)
            radius: Style.cornerRadius
            anchors.verticalCenter: parent.verticalCenter
            color: root.findingsCount > 0 ? root.urgentFill(0.15)
              : root.hooksSeen ? root.accentFill(0.12)
              : root.fgFill(0.06)
            border.color: root.findingsCount > 0 ? root.urgentFill(0.5)
              : root.hooksSeen ? root.accentFill(0.45)
              : root.fgFill(0.15)

            Text {
              id: statusText
              anchors.centerIn: parent
              textFormat: Text.PlainText
              text: root.findingsCount > 0
                ? root.findingsCount + " FINDING" + (root.findingsCount === 1 ? "" : "S")
                : root.hooksSeen ? "LIVE"
                : root.probed ? "SETUP" : "···"
              color: root.findingsCount > 0 ? root.urgent
                : root.hooksSeen ? root.accent : root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }
          }
        }

        // ---- setup banner (dayflow error-banner look) ----
        // Stays above the tabs — the tabs remain visible/usable either way.
        Rectangle {
          visible: root.needsSetup
          width: parent.width - content.leftPadding - content.rightPadding
          height: setupColumn.implicitHeight + Style.space(20)
          radius: Style.cornerRadius
          color: root.fgFill(0.04)
          border.color: root.fgFill(0.10)

          Column {
            id: setupColumn
            width: parent.width - Style.space(24)
            anchors.centerIn: parent
            spacing: Style.space(6)

            Text {
              width: parent.width
              text: "! " + (root.installed ? "hooks not installed" : "numbat not installed")
              textFormat: Text.PlainText
              color: root.urgent
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              font.bold: true
              wrapMode: Text.WordWrap
            }

            Text {
              width: parent.width
              text: root.probeError !== "" ? "! " + root.probeError
                : root.installed
                  ? "numbat is installed, but no hook events have been recorded yet. Install the hooks once and agent activity shows up here automatically."
                  : "numbat watches coding-agent hooks and records what they do. Get the CLI at github.com/perplexityai/numbat/releases, then run `numbat hook install --agent all`."
              textFormat: Text.PlainText
              color: root.probeError !== "" ? root.urgent : root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }

            // A user instruction, not a live command — PlainText, never exec'd.
            Rectangle {
              visible: root.installed && !root.hooksSeen
              width: parent.width
              height: Style.space(30)
              radius: Style.cornerRadius
              color: root.fgFill(0.05)
              border.color: root.accentFill(0.25)

              Text {
                anchors.centerIn: parent
                text: "run: numbat hook install --agent all"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }
            }
          }
        }

        // ---- pill tab bar ----
        Row {
          width: parent.width - content.leftPadding - content.rightPadding
          spacing: Style.space(6)

          Repeater {
            model: [
              { id: "activity", label: "Activity" },
              { id: "findings", label: "Findings" },
              { id: "log", label: "Log" }
            ]

            delegate: Rectangle {
              height: Style.space(28)
              width: tabLabel.implicitWidth + Style.space(16)
              radius: Style.cornerRadius
              color: root.currentTab === modelData.id
                ? root.accentFill(0.12)
                : (tabMouse.containsMouse ? root.accentFill(0.06) : "transparent")
              border.color: root.currentTab === modelData.id
                ? root.accentFill(0.45)
                : "transparent"

              Text {
                id: tabLabel
                anchors.centerIn: parent
                text: modelData.label
                textFormat: Text.PlainText
                color: root.currentTab === modelData.id ? root.foreground : root.dim
                font.bold: root.currentTab === modelData.id
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }

              MouseArea {
                id: tabMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.currentTab = modelData.id
              }
            }
          }
        }

        PanelSeparator { foreground: root.foreground }

        // ---- tab content (bounded scroll; card never outgrows the screen) ----
        Flickable {
          width: parent.width - content.leftPadding - content.rightPadding
          height: Math.min(Style.space(380), tabLoader.item ? tabLoader.item.implicitHeight : Style.space(80))
          contentWidth: width
          contentHeight: tabLoader.item ? tabLoader.item.implicitHeight : 0
          clip: true

          Loader {
            id: tabLoader
            width: parent.width
            sourceComponent: root.currentTab === "activity" ? activityTab
              : root.currentTab === "findings" ? findingsTab
              : logTab
          }
        }

        PanelSeparator { foreground: root.foreground }

        // ---- status footer ----
        Text {
          width: parent.width - content.leftPadding - content.rightPadding
          text: !root.probed ? "probing numbat…"
            : root.activeAgents.length + " agent" + (root.activeAgents.length === 1 ? "" : "s")
              + " · " + root.findingsCount + " finding" + (root.findingsCount === 1 ? "" : "s") + "/24h"
              + (root.events.length > 0 ? " · " + root.events.length + " events" : "")
              + (root.recordsPath !== "" ? " · " + root.recordsPath : "")
              + (root.isRefreshing ? " · refreshing" : "")
          textFormat: Text.PlainText
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }

  // ---- tab components ----

  Component {
    id: activityTab

    Column {
      width: parent ? parent.width : 0
      spacing: Style.space(6)

      PanelSectionHeader { text: "ACTIVE AGENTS"; foreground: root.foreground; fontFamily: root.fontFamily }

      Text {
        visible: root.activeAgents.length === 0
        width: parent.width
        // A user instruction, not a live command — PlainText, never exec'd.
        text: "No agent activity recorded — run `numbat hook install --agent all`"
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Repeater {
        model: root.activeAgents

        delegate: Rectangle {
          width: parent.width
          height: Style.space(46)
          radius: Style.cornerRadius
          color: root.fgFill(0.04)
          border.color: root.fgFill(0.08)

          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Style.space(12)
            anchors.rightMargin: Style.space(12)
            spacing: Style.space(10)

            Rectangle {
              Layout.preferredWidth: Style.space(8)
              Layout.preferredHeight: Style.space(8)
              radius: width / 2
              color: root.accent
            }

            Column {
              Layout.fillWidth: true
              spacing: Style.space(2)

              Text {
                width: parent.width
                text: modelData.name || "unnamed agent"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                text: "last event " + root.relTime(modelData.last_event)
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }
          }
        }
      }
    }
  }

  Component {
    id: findingsTab

    Column {
      width: parent ? parent.width : 0
      spacing: Style.space(6)

      PanelSectionHeader { text: "FINDINGS · 24H"; foreground: root.foreground; fontFamily: root.fontFamily }

      Text {
        visible: root.findings.length === 0
        width: parent.width
        text: "No findings in the last 24h"
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Repeater {
        model: root.findings

        delegate: Rectangle {
          width: parent.width
          height: Style.space(46)
          radius: Style.cornerRadius
          color: root.fgFill(0.04)
          border.color: root.severe(modelData) ? root.urgentFill(0.45) : root.fgFill(0.08)

          // Left-border accent: urgent when the record's severity is
          // meaningful, a uniform faint strip otherwise.
          Rectangle {
            width: Style.space(3)
            height: parent.height - Style.space(16)
            radius: width / 2
            anchors.left: parent.left
            anchors.leftMargin: Style.space(6)
            anchors.verticalCenter: parent.verticalCenter
            color: root.severe(modelData) ? root.urgent : root.fgFill(0.14)
          }

          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Style.space(16)
            anchors.rightMargin: Style.space(12)
            spacing: Style.space(10)

            Column {
              Layout.fillWidth: true
              spacing: Style.space(2)

              Text {
                width: parent.width
                text: modelData.rule || "unnamed rule"
                textFormat: Text.PlainText
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                text: (modelData.agent || "unknown agent") + " · " + root.relTime(modelData.observed_at)
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }
          }
        }
      }
    }
  }

  Component {
    id: logTab

    Column {
      width: parent ? parent.width : 0
      spacing: Style.space(6)

      PanelSectionHeader { text: "RECENT EVENTS"; foreground: root.foreground; fontFamily: root.fontFamily }

      Text {
        visible: root.events.length === 0
        width: parent.width
        text: "No events recorded yet"
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Repeater {
        model: root.events

        delegate: Rectangle {
          width: parent.width
          height: Style.space(34)
          radius: Style.cornerRadius
          color: root.fgFill(0.04)
          border.color: root.fgFill(0.08)

          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Style.space(12)
            anchors.rightMargin: Style.space(12)
            spacing: Style.space(10)

            Text {
              text: modelData.agent || "unknown"
              textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              elide: Text.ElideRight
              Layout.maximumWidth: Style.space(130)
            }

            Text {
              Layout.fillWidth: true
              text: (modelData.kind || "event") + (modelData.summary ? " · " + modelData.summary : "")
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }

            Text {
              text: root.relTime(modelData.observed_at)
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
          }
        }
      }
    }
  }
}
