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
  // manageIpc: false so this panel can own the single IpcHandler the target
  // gets — the service's finding toasts call `open` via `qs ipc`.
  manageIpc: false

  property bool probed: false
  property bool installed: false
  property bool hooksSeen: false
  property int findingsCount: 0
  property var findings: []
  property var activeAgents: []
  property var agentsSeen: []
  property var hookedAgents: []
  property var events: []
  property bool eventsLive: false
  property string recordsPath: ""
  property double recordsBytes: 0
  property double findingsBytes: 0
  property double recordsRateBpd: -1
  property bool recordsRotHint: false
  property string probeError: ""
  property string scanError: ""
  property bool isRefreshing: false
  property bool isReviewing: false
  property string jevSummary: ""
  property string jevError: ""
  property string jevModel: ""
  property int jevEventCount: 0
  property string currentTab: "activity" // "activity" | "findings" | "log" | "review"
  property string agentFilter: ""

  // Persisted shell.json entry for this plugin — same LocalSettings the
  // service uses. The panel writes `lastPanelSeen` (ms epoch) on open;
  // findings newer than it drive the bar badge count.
  LocalSettings { id: ls; pluginId: root.moduleName }

  // Unseen = findings newer than the last time the panel was opened.
  // Watermark advances on open, so the badge always means "new since you
  // last looked", not "new in the file".
  readonly property int unseenCount: {
    var e = ls.loaded ? ls.entry : null
    var wm = e ? Number(e.lastPanelSeen) || 0 : 0
    var n = 0
    for (var i = 0; i < findings.length; i++) {
      var ms = new Date(String(findings[i].observed_at || "")).getTime()
      if (isFinite(ms) && ms > wm) n++
    }
    return n
  }

  // Distinct agents across the current feed, first-seen order (bounded).
  readonly property var filterAgents: {
    var seen = {}, out = []
    for (var i = 0; i < findings.length; i++) {
      var a = String(findings[i].agent || "unknown agent")
      if (!seen[a]) { seen[a] = true; out.push(a) }
    }
    return out.slice(0, 8)
  }

  // Feed as filtered by the agent chip row; "" shows everything.
  readonly property var feedFindings: {
    if (agentFilter === "") return findings
    return findings.filter(function (f) {
      return String(f.agent || "unknown agent") === agentFilter
    })
  }

  readonly property string rotateCommand: "mv ~/.numbat/records.ndjson ~/.numbat/records.ndjson.old"

  function markPanelSeen() {
    // Before settings load (or after unparseable JSON) the entry is empty, and
    // writing it would drop toastMinSeverity/toastCooldownS.
    if (!ls.loaded) return
    var cur = ls.entry
    var entry = {}
    if (cur && typeof cur === "object" && !Array.isArray(cur)) {
      for (var k in cur) entry[k] = cur[k]
    }
    entry.lastPanelSeen = Date.now()
    ls.remember(entry)
    if (root.bar && root.bar.shell
        && typeof root.bar.shell.updateEntryInline === "function") {
      try { root.bar.shell.updateEntryInline(root.moduleName, entry) }
      catch (e) { console.warn("numbat: could not persist lastPanelSeen: " + e) }
    }
  }

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

  function runJevReview() {
    if (jevProc.running) return
    isReviewing = true
    jevSummary = ""
    jevError = ""
    jevModel = ""
    jevEventCount = 0
    jevProc.running = true
    jevDeadline.restart()
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

  function humanBytes(n) {
    if (!isFinite(n) || n < 0) return "?"
    var units = ["B", "KiB", "MiB", "GiB", "TiB"], i = 0
    while (n >= 1024 && i < units.length - 1) { n = n / 1024; i++ }
    return (i === 0 ? String(n) : n.toFixed(n >= 100 ? 0 : 1)) + " " + units[i]
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

  // Same severity map the service toasts use — unknown/empty -> medium.
  function sevRank(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev).toLowerCase()
    if (s === "critical" || s === "crit") return 4
    if (s === "high" || s === "error") return 3
    if (s === "medium" || s === "moderate" || s === "warning" || s === "warn") return 2
    if (s === "low") return 1
    if (s === "info" || s === "debug" || s === "none") return 0
    return 2
  }

  // Chip label/color for a finding's severity. Empty severity -> no chip
  // ("" label), never a fabricated "MED".
  function sevLabel(sev) {
    var s = String(sev === undefined || sev === null ? "" : sev)
    s = s.replace(/^\s+|\s+$/g, "").toUpperCase()
    return s.substring(0, 4)
  }

  function sevColor(sev) {
    var r = sevRank(sev)
    if (r >= 3) return root.urgent
    if (r === 2) return root.accent
    return root.dim
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

  IpcHandler {
    target: "io.github.duketopceo.numbat"

    function open() { root.open() }
    function close() { root.close() }
    function show() { root.open() }
    function hide() { root.close() }
    function toggle() { root.toggle() }
  }

  onOpenedChanged: if (opened) { root.refresh(); root.markPanelSeen() }

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
          root.agentsSeen = (Array.isArray(data.agents_seen) ? data.agents_seen : []).slice(0, 10)
          root.hookedAgents = (Array.isArray(data.hooked_agents) ? data.hooked_agents : []).slice(0, 32)
          root.events = (Array.isArray(data.events) ? data.events : []).slice(0, 30)
          root.eventsLive = data.events_live === true
          root.recordsPath = typeof data.records_path === "string" ? data.records_path : ""
          root.recordsBytes = Math.max(0, Number(data.records_bytes) || 0)
          root.findingsBytes = Math.max(0, Number(data.findings_bytes) || 0)
          root.recordsRateBpd = (typeof data.records_rate_bpd === "number" && data.records_rate_bpd !== null)
              ? Math.max(0, data.records_rate_bpd) : -1
          root.recordsRotHint = data.records_rot_hint === true
          root.probeError = typeof data.error === "string" && data.error !== null ? data.error : ""
          root.scanError = typeof data.scan_error === "string" ? data.scan_error : ""
        } catch (e) {}
      }
    }
    // Helper tracebacks land here — collect so a probe crash is visible
    // in the journal instead of looking like a dead widget.
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("probe_numbat stderr: " + err.substring(0, 500))
      }
    }
    onExited: {
      statusDeadline.stop()
      root.isRefreshing = false
    }
  }
  // Hard whole-job deadline — last-resort backstop, set just past the
  // helper's own JOB_DEADLINE_S (62s; worst-case work is ~59s =
  // SCAN_TIMEOUT_S 55 + HOOKS_TIMEOUT_S 3 + tail reads). A tighter bound
  // group-kills slow-but-healthy scans before the single-shot stdout.write
  // and strands the panel at "probing numbat…". probe_numbat.py calls
  // os.setsid() and keeps helpers in its own session group, so a group-kill
  // still reaches the whole tree if Python is wedged in a wait.
  Timer {
    id: statusDeadline
    interval: 70000
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

  Process {
    id: jevProc
    command: [root.py, root.pluginRoot + "/bin/jev_review.py"]
    clearEnvironment: true
    environment: Object.assign({}, root.procEnv, {
      "OPENROUTER_API_KEY": null
    })
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        jevDeadline.stop()
        root.isReviewing = false
        try {
          if (!text || text.trim().length === 0) return
          var data = JSON.parse(text)
          if (typeof data !== "object" || data === null) return
          root.jevSummary = typeof data.summary === "string" ? data.summary : ""
          root.jevError = typeof data.error === "string" ? data.error : ""
          root.jevModel = typeof data.model === "string" ? data.model : ""
          root.jevEventCount = Math.max(0, Number(data.event_count) || 0)
        } catch (e) {}
      }
    }
    onExited: {
      jevDeadline.stop()
      root.isReviewing = false
    }
  }

  Timer {
    id: jevDeadline
    interval: 50000
    onTriggered: {
      if (jevProc.running) {
        var pid = jevProc.pid
        if (pid > 0)
          Quickshell.execDetached(["/usr/bin/kill", "-KILL", "--", "-" + pid.toString()])
        jevProc.signal(9)
        root.isReviewing = false
        root.jevError = "Jev review timed out"
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

  // Unseen-findings badge over the bar glyph. Counts records newer than
  // lastPanelSeen; hidden at zero.
  Rectangle {
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.rightMargin: -Style.space(2)
    anchors.topMargin: -Style.space(2)
    width: Math.max(Style.space(14), badgeText.implicitWidth + Style.space(8))
    height: Style.space(13)
    radius: height / 2
    visible: root.unseenCount > 0
    color: root.urgent
    border.color: root.fgFill(0.2)

    Text {
      id: badgeText
      anchors.centerIn: parent
      text: root.unseenCount > 9 ? "9+" : String(root.unseenCount)
      textFormat: Text.PlainText
      color: Color.background
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption - 2
      font.bold: true
    }
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
                  : "numbat watches coding-agent hooks and records what they do. Get the CLI at github.com/perplexityai/numbat/releases, then run `numbat hook install --agent all --emit all`."
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
                text: "run: numbat hook install --agent all --emit all"
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
              { id: "log", label: "Log" },
              { id: "review", label: "Jev" }
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
              : root.currentTab === "review" ? reviewTab
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
        text: "No agent activity recorded — run `numbat hook install --agent all --emit all`"
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

      PanelSeparator { foreground: root.foreground }

      PanelSectionHeader { text: "MONITORED" + (root.hookedAgents.length > 0 ? " · " + root.hookedAgents.length + " WIRED" : ""); foreground: root.foreground; fontFamily: root.fontFamily }

      Text {
        visible: root.agentsSeen.length === 0 && root.hookedAgents.length === 0
        width: parent.width
        text: "No agent coverage yet"
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Text {
        visible: root.hookedAgents.length > 0
        width: parent.width
        // Wired agents with numbat-owned hooks/plugins — coverage, not activity.
        text: "hooks wired: " + root.hookedAgents.join(", ")
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Repeater {
        model: root.agentsSeen

        delegate: Rectangle {
          width: parent.width
          height: Style.space(34)
          radius: Style.cornerRadius
          color: root.fgFill(0.03)
          border.color: root.fgFill(0.06)

          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Style.space(12)
            anchors.rightMargin: Style.space(12)
            spacing: Style.space(10)

            Rectangle {
              Layout.preferredWidth: Style.space(6)
              Layout.preferredHeight: Style.space(6)
              radius: width / 2
              color: root.dim
            }

            Text {
              Layout.fillWidth: true
              text: modelData.name || "unnamed agent"
              textFormat: Text.PlainText
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              elide: Text.ElideRight
            }

            Text {
              text: root.relTime(modelData.last_event)
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

  Component {
    id: findingsTab

    Column {
      width: parent ? parent.width : 0
      spacing: Style.space(6)

      PanelSectionHeader { text: "FINDINGS · 24H"; foreground: root.foreground; fontFamily: root.fontFamily }

      // Agent filter chips — only worth showing when >1 agent produced
      // findings. "ALL" resets to the unfiltered feed.
      Row {
        visible: root.filterAgents.length > 1
        spacing: Style.space(4)

        Repeater {
          model: ["ALL"].concat(root.filterAgents)

          delegate: Rectangle {
            readonly property bool on: (modelData === "ALL")
                ? root.agentFilter === ""
                : root.agentFilter === modelData
            height: Style.space(18)
            width: chipText.implicitWidth + Style.space(10)
            radius: height / 2
            color: on ? root.accentFill(0.30) : root.fgFill(0.06)
            border.color: on ? root.accentFill(0.60) : root.fgFill(0.10)

            Text {
              id: chipText
              anchors.centerIn: parent
              text: String(modelData).substring(0, 12)
              textFormat: Text.PlainText
              color: parent.on ? root.accent : root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }

            MouseArea {
              anchors.fill: parent
              onClicked: root.agentFilter = modelData === "ALL" ? "" : String(modelData)
            }
          }
        }
      }

      Text {
        visible: root.findings.length === 0
        width: parent.width
        text: "No findings in the last 24h"
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Text {
        visible: root.findings.length > 0 && root.feedFindings.length === 0
        width: parent.width
        text: "No findings from " + root.agentFilter
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      Repeater {
        model: root.feedFindings

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

            // Severity chip — only when the record carried the field;
            // color shares the toast rank map.
            Rectangle {
              readonly property string lbl: root.sevLabel(modelData.severity)
              visible: lbl !== ""
              Layout.alignment: Qt.AlignVCenter
              width: sevChipText.implicitWidth + Style.space(8)
              height: Style.space(16)
              radius: height / 2
              color: root.sevColor(modelData.severity) === root.urgent
                     ? root.urgentFill(0.20) : root.fgFill(0.08)
              border.color: root.sevColor(modelData.severity)

              Text {
                id: sevChipText
                anchors.centerIn: parent
                text: parent.lbl
                textFormat: Text.PlainText
                color: root.sevColor(modelData.severity)
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption - 2
                font.bold: true
              }
            }
          }
        }
      }
    }
  }

  Component {
    id: reviewTab

    Column {
      width: parent ? parent.width : 0
      spacing: Style.space(8)

      PanelSectionHeader { text: "JEV AGENT REVIEW"; foreground: root.foreground; fontFamily: root.fontFamily }

      Text {
        width: parent.width
        text: "TypeSafe Jev reads recent numbat events and flags useless tool calls, wrong thinking, and wasted time. Requires OPENROUTER_API_KEY."
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Rectangle {
        width: parent.width
        height: Style.space(32)
        radius: Style.cornerRadius
        color: root.isReviewing ? root.accentFill(0.10) : root.accentFill(0.18)
        border.color: root.accentFill(0.45)

        Text {
          anchors.centerIn: parent
          text: root.isReviewing ? "Reviewing with Jev…" : "Run Jev review"
          textFormat: Text.PlainText
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          font.bold: true
        }

        MouseArea {
          anchors.fill: parent
          enabled: !root.isReviewing
          cursorShape: Qt.PointingHandCursor
          onClicked: root.runJevReview()
        }
      }

      Text {
        visible: root.jevError !== ""
        width: parent.width
        text: root.jevError
        textFormat: Text.PlainText
        color: root.urgent
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      Text {
        visible: root.jevSummary !== "" && root.jevError === ""
        width: parent.width
        text: root.jevSummary
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        wrapMode: Text.WordWrap
      }

      Text {
        visible: root.jevModel !== "" && root.jevError === ""
        width: parent.width
        text: root.jevEventCount + " events · " + root.jevModel
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
  }

  Component {
    id: logTab

    Column {
      width: parent ? parent.width : 0
      spacing: Style.space(6)

      PanelSectionHeader { text: "RECORD FILE"; foreground: root.foreground; fontFamily: root.fontFamily }

      Text {
        width: parent.width
        text: "records.ndjson · " + root.humanBytes(root.recordsBytes)
              + (root.recordsRateBpd >= 0 ? " · ~" + root.humanBytes(root.recordsRateBpd) + "/day" : "")
              + (root.findingsBytes > 0 ? "  |  findings.ndjson · " + root.humanBytes(root.findingsBytes) : "")
        textFormat: Text.PlainText
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
      }

      Row {
        visible: root.recordsRotHint
        width: parent.width
        spacing: Style.space(8)

        Text {
          width: parent.width - rotCopy.width - parent.spacing
          text: "Large — numbat has no rotation yet. Copy the rotate command and run it by hand (the plugin stays read-only on ~/.numbat)."
          textFormat: Text.PlainText
          color: root.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
          anchors.verticalCenter: parent.verticalCenter
        }

        Rectangle {
          id: rotCopy
          height: Style.space(22)
          width: rotCopyText.implicitWidth + Style.space(12)
          radius: Style.cornerRadius
          color: mRotCopy.containsMouse ? root.accentFill(0.12) : "transparent"
          border.color: root.accentFill(0.5)
          anchors.verticalCenter: parent.verticalCenter

          Text {
            id: rotCopyText
            anchors.centerIn: parent
            text: "copy cmd"
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
          MouseArea {
            id: mRotCopy
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: Quickshell.execDetached(
              ["/usr/bin/wl-copy", "--", root.rotateCommand])
          }
        }
      }

      // Selectable fallback for when wl-copy is missing or the copy fails.
      TextEdit {
        visible: root.recordsRotHint
        width: parent.width
        text: root.rotateCommand
        textFormat: TextEdit.PlainText
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.WrapAnywhere
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }

      // STREAMED = records.ndjson (--emit all hooks) is the live feed;
      // SCANNED = only the 10-min scan cache is feeding the list.
      PanelSectionHeader { text: "RECENT EVENTS" + (root.probed ? " · " + (root.eventsLive ? "STREAMED" : "SCANNED") : ""); foreground: root.foreground; fontFamily: root.fontFamily }

      Text {
        visible: root.events.length === 0
        width: parent.width
        text: root.scanError !== "" ? root.scanError : "No events recorded yet"
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
