import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "lib"

Panel {
  id: root
  moduleName: "lukedaduke.fan"
  ipcTarget: "lukedaduke.fan"

  // --- fan mode -------------------------------------------------------------
  property string currentMode: "auto"
  property string customName: "balanced"

  // --- bar data (cheap `--bar` run, at most once a minute) -------------------
  property int memPct: 0
  property string memUsed: "--"
  property string memTotal: "--"
  property int tempC: -1
  property string tempLabel: ""
  property string tempSource: "none"
  property var fanList: []

  // --- panel data (full run, every 5 s while the panel is open) --------------
  property string cpuName: "CPU"
  property int cpuLoad: 0
  property var cpuCores: []
  property int cpuTemp: -1
  property string memAvail: "--"
  property string swapUsed: "--"
  property string swapTotal: "--"
  property string ramType: ""
  property string gpuName: ""
  property int gpuLoad: -1
  property string gpuReason: ""
  property int gpuTemp: -1
  property real gpuPowerW: -1
  property var gpuClients: []
  property var temps: []
  property int nvmeTemp: -1
  property var disks: []
  property var groups: []
  property bool warm: false
  property var fanCurve: []
  property bool hasFullData: false

  property string fetchError: ""
  property string statsStderr: ""

  // --- process list interaction -------------------------------------------------
  property int selectedGroup: 0
  property string expandedLabel: ""
  property int armedKillPid: 0
  property string killStatus: ""
  property string killLabel: ""

  // Fan control is owned by the omarchy-fan-helper package (root, from
  // /usr/lib/omarchy-fan). The plugin never installs or elevates it: it only
  // reads the helper's status and asks for a package install/update.
  readonly property string expectedHelperVersion: "1.0.0"
  // "missing" | "outdated" | "ok"
  property string helperState: "missing"
  property string helperVersion: ""
  property bool helperControllable: false
  property string helperMode: ""
  // A mode the user just requested; the helper status lags by up to one tick,
  // so readHelperStatus must not revert currentMode until it catches up.
  property string pendingMode: ""
  property real pendingUntil: 0
  property var queuedFanArgs: null
  readonly property bool fanControl: root.helperState === "ok" && root.helperControllable
  readonly property bool helperModeActive: root.helperState === "ok" && root.helperMode.length > 0

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property color muted: Color.muted
  readonly property color dim: Qt.darker(root.fg, 1.4)
  readonly property string fontFamily: root.bar ? root.bar.fontFamily : Style.font.family

  // Absolute interpreter: a PATH-preceding shadow "python3" must never run
  // inside this long-lived shell process.
  readonly property string py: "/usr/bin/python3"
  readonly property string binDir: pluginPath.path + "/bin"

  PluginRoot {
    id: pluginPath
    url: Qt.resolvedUrl(".")
  }

  // Minimal helper env. Keeps XDG_RUNTIME_DIR so the collector and
  // omarchy-fan-set agree on $XDG_RUNTIME_DIR/omarchy-fan/, and HOME for the
  // custom curve file.
  ProcEnv {
    id: procEnv
  }

  VisibilityGate {
    id: gate
    shell: root.bar ? root.bar.shell : null
    panelOpen: root.opened
    onRevealed: root.refreshBar()
  }

  StaleLabel {
    id: freshness
    intervalMs: root.opened ? 5000 : 60000
  }

  // --- helpers ------------------------------------------------------------------

  // Cap + normalize helper strings before they reach Text sinks.
  function clipStr(v, n) {
    return String(v === undefined || v === null ? "" : v).replace(/[\x00-\x1f\x7f-\x9f<>]/g, " ").slice(0, n || 80)
  }

  function num(v, fallback) {
    var n = Number(v)
    return isFinite(n) ? n : fallback
  }

  function intOr(v, fallback) {
    return (v === null || v === undefined || !isFinite(Number(v))) ? fallback : Math.round(Number(v))
  }

  function pct(v) {
    return Math.max(0, Math.min(100, Math.round(num(v, 0))))
  }

  function kindGlyph(kind) {
    if (kind === "browser") return "󰖟"
    if (kind === "agent") return "󰚩"
    if (kind === "dev") return "󰅩"
    if (kind === "shell") return "󰍹"
    if (kind === "system") return "󰒓"
    if (kind === "plugin") return "󰐱"
    return "󰀻"
  }

  function memText(mb) {
    var m = num(mb, 0)
    return m >= 1024 ? (m / 1024).toFixed(1) + " GB" : Math.round(m) + " MB"
  }

  function levelColor(value, warn, crit) {
    if (value < 0 || isNaN(value)) return root.muted
    if (value >= crit) return root.urgent
    if (value >= warn) return root.accent
    return root.fg
  }

  function tempText(c) {
    return c >= 0 ? c + "°C" : "--"
  }

  function modeLetter() {
    var m = root.currentMode
    return m === "auto" ? "A" : (m === "high" ? "H" : (m === "med" ? "M" : (m === "custom" ? "C" : "L")))
  }

  function fanSummary() {
    if (!root.fanList || root.fanList.length === 0) return "no fan sensors"
    return root.fanList.map(function(f) { return f.label + " " + f.rpm + " rpm" }).join(" · ")
  }

  // --- helper status (spawn-free) ---------------------------------------------------

  // loaded=false: the status file is gone (helper not installed or stopped).
  function readHelperStatus(loaded) {
    var raw = ""
    if (loaded) {
      try {
        raw = String(helperStatusFile.text() || "")
      } catch (e) {
        raw = ""
      }
    }
    var data = null
    if (raw.length > 0 && raw.length < 4096) {
      try {
        data = JSON.parse(raw)
      } catch (e2) {
        data = null
      }
    }
    if (!data || typeof data !== "object") {
      root.helperState = "missing"
      root.helperVersion = ""
      root.helperControllable = false
      root.helperMode = ""
      return
    }
    root.helperVersion = clipStr(data.version, 24)
    root.helperState = root.helperVersion === root.expectedHelperVersion ? "ok" : "outdated"
    root.helperControllable = data.controllable === true
    root.helperMode = clipStr(data.mode, 24).trim()
    if (root.pendingMode.length > 0 && (root.helperMode === root.pendingMode || Date.now() > root.pendingUntil))
      root.pendingMode = ""
    if (root.helperModeActive && root.pendingMode.length === 0)
      root.currentMode = root.helperMode
  }

  function helperHint() {
    if (root.helperState === "missing")
      return "Fan control needs the omarchy-fan-helper package: install it, then run 'systemctl enable --now omarchy-fan-daemon.service'."
    if (root.helperState === "outdated")
      return "Update the omarchy-fan-helper package (have " + (root.helperVersion || "?") + ", need " + root.expectedHelperVersion + ")."
    if (!root.helperControllable)
      return "This machine exposes no writable fan target; fans stay on firmware control."
    return "Silent auto curve by default. Fixed presets fall back to auto if the shell goes away."
  }

  // --- fan mode requests ---------------------------------------------------------------

  function runFanSet(args) {
    var argv = [root.py, root.binDir + "/omarchy-fan-set"].concat(args)
    if (fanSetProc.running) {
      root.queuedFanArgs = argv
      return
    }
    fanSetProc.command = argv
    fanSetProc.start()
  }

  function setMode(mode) {
    // "auto" is always safe to write, so it bypasses the fanControl guard
    // whenever a helper is present (e.g. version drift with a pinned preset).
    if (!mode || !(root.fanControl || (mode === "auto" && root.helperState !== "missing")))
      return
    root.currentMode = mode
    root.pendingMode = mode
    root.pendingUntil = Date.now() + 6000
    root.runFanSet([mode])
  }

  function setCustom(name) {
    if (!root.fanControl)
      return
    root.currentMode = "custom"
    root.pendingMode = "custom"
    root.pendingUntil = Date.now() + 6000
    root.customName = name
    root.runFanSet(["custom", name])
  }

  function cycleMode() {
    if (!root.fanControl)
      return
    var order = ["auto", "low", "med", "high", "custom"]
    var from = root.pendingMode.length > 0 ? root.pendingMode : root.currentMode
    var i = order.indexOf(from)
    root.setMode(order[(i + 1) % order.length])
  }

  // --- stats ------------------------------------------------------------------------------

  function refreshBar() {
    helperStatusFile.reload()
    if (!root.opened)
      barProc.start()
  }

  function refreshFull() {
    helperStatusFile.reload()
    freshness.nowMs = Date.now()
    fullProc.start()
  }

  function failed(message) {
    root.fetchError = clipStr(message, 120)
    freshness.markFailed()
  }

  function ingest(text, full) {
    var raw = String(text || "")
    if (raw.trim().length === 0) return root.failed("empty stats")
    if (raw.length > 300000) return root.failed("oversized stats payload")
    var env = null
    try {
      env = JSON.parse(raw)
    } catch (e) {
      return root.failed("bad stats json")
    }
    if (!env || env.ok !== true || !env.data)
      return root.failed("stats: " + (env && env.error ? env.error : "failed"))
    var d = env.data
    var caps = env.capabilities || {}

    var mem = d.mem || {}
    root.memPct = pct(mem.pct)
    root.memUsed = num(mem.used_gb, 0).toFixed(1)
    root.memTotal = num(mem.total_gb, 0).toFixed(1)
    var t = d.temp || {}
    root.tempC = intOr(t.c, -1)
    root.tempLabel = clipStr(t.label, 40)
    root.tempSource = clipStr(t.source, 8)
    if (Array.isArray(d.fans))
      root.fanList = d.fans.slice(0, 6).map(function(f) {
        return { "label": clipStr(f.label, 32), "rpm": Math.max(0, intOr(f.rpm, 0)) }
      })
    // The helper's effective mode wins: an expired preset shows as auto.
    if (d.fan_mode && !root.helperModeActive && root.pendingMode.length === 0)
      root.currentMode = clipStr(d.fan_mode, 24).trim()

    if (full) {
      var cpu = d.cpu || {}
      root.cpuName = clipStr(cpu.name, 48) || "CPU"
      root.cpuLoad = pct(cpu.load)
      root.cpuCores = Array.isArray(cpu.cores) ? cpu.cores.slice(0, 128).map(function(c) {
        return { "core": intOr(c.core, 0), "percent": pct(c.percent) }
      }) : []
      root.cpuTemp = intOr(cpu.temp, -1)
      root.memAvail = num(mem.avail_gb, 0).toFixed(1)
      root.swapUsed = num(mem.swap_used_gb, 0).toFixed(1)
      root.swapTotal = num(mem.swap_total_gb, 0).toFixed(1)
      root.ramType = clipStr(mem.type, 32)
      var g = d.gpu || {}
      root.gpuName = clipStr(g.name, 48)
      root.gpuLoad = (g.load === null || g.load === undefined) ? -1 : pct(g.load)
      root.gpuReason = clipStr(g.reason, 90)
      root.gpuTemp = intOr(g.temp, -1)
      root.gpuPowerW = (typeof g.power_w === "number") ? g.power_w : -1
      root.gpuClients = Array.isArray(g.clients) ? g.clients.slice(0, 8).map(function(c) {
        return clipStr(c.label, 32) + (intOr(c.count, 1) > 1 ? " ×" + intOr(c.count, 1) : "")
      }) : []
      root.temps = Array.isArray(d.temps) ? d.temps.slice(0, 8).map(function(x) {
        return { "label": clipStr(x.label, 40), "c": intOr(x.c, -1) }
      }) : []
      root.nvmeTemp = intOr(d.nvme_temp, -1)
      root.disks = Array.isArray(d.disks) ? d.disks.slice(0, 16).map(function(x) {
        return { "mount": clipStr(x.mount, 64), "used": num(x.used_gb, 0), "total": num(x.total_gb, 0), "percent": pct(x.percent) }
      }) : []
      root.groups = Array.isArray(d.groups) ? d.groups.slice(0, 16).map(function(x) {
        return {
          "label": clipStr(x.label, 40),
          "kind": clipStr(x.kind, 12),
          "detail": clipStr(x.detail, 90),
          "cpu": Math.max(0, num(x.cpu, 0)),
          "mem": Math.max(0, num(x.mem_mb, 0)),
          "count": Math.max(1, intOr(x.count, 1)),
          "pids": Array.isArray(x.pids) ? x.pids.slice(0, 3).map(function(p) { return intOr(p, 0) }) : [],
          "killPid": intOr(x.kill_pid, 0),
          "killStart": intOr(x.kill_start, 0)
        }
      }) : []
      root.warm = d.warm === true
      if (Array.isArray(d.fan_curve))
        root.fanCurve = d.fan_curve.slice(0, 64)
      root.hasFullData = true
      if (root.selectedGroup >= root.groups.length)
        root.selectedGroup = Math.max(0, root.groups.length - 1)
    }
    root.fetchError = ""
    freshness.markGood()
  }

  function processExited(proc, code) {
    if (proc.timedOut)
      root.failed("stats timeout")
    else if (code !== 0)
      root.failed(root.statsStderr.length > 0 ? "stats helper failed: " + root.statsStderr : "stats helper exited " + code)
    root.statsStderr = ""
  }

  // --- kill ----------------------------------------------------------------------------------

  function selected() {
    return root.groups[root.selectedGroup] || null
  }

  // First press arms, second press within 5 s kills. Only single-process
  // groups carry a kill target; the start time guards against pid reuse.
  function requestKill(g) {
    if (!g || g.killPid <= 1)
      return
    if (root.armedKillPid !== g.killPid) {
      root.armedKillPid = g.killPid
      disarmTimer.restart()
      return
    }
    root.armedKillPid = 0
    disarmTimer.stop()
    if (killProc.running)
      return
    root.killLabel = g.label
    root.killStatus = "Stopping " + g.label + "…"
    killProc.command = [root.py, root.binDir + "/kill_proc.py", String(g.killPid), String(g.killStart)]
    killProc.start()
  }

  function killResult(text) {
    var env = null
    try {
      env = JSON.parse(String(text || ""))
    } catch (e) {
      env = null
    }
    if (env && env.ok === true)
      root.killStatus = "Stopped " + root.killLabel
    else {
      var why = env && env.error ? String(env.error) : "failed"
      var words = { "permission": "not your process", "gone": "already exited", "changed": "pid now belongs to another process", "refused": "refused" }
      root.killStatus = "Could not stop " + root.killLabel + ": " + clipStr(words[why] || why, 60)
    }
    if (root.opened)
      root.refreshFull()
  }

  function toggleExpanded(g) {
    if (!g) return
    root.expandedLabel = root.expandedLabel === g.label ? "" : g.label
  }

  function btop() {
    if (bar)
      bar.run("omarchy-launch-or-focus-tui btop")
    root.close()
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  // --- processes (DeadlineProcess: deadline + group kill + ProcEnv) -------------------------------

  DeadlineProcess {
    id: barProc
    deadlineMs: 9000
    environment: procEnv.env
    command: [root.py, root.binDir + "/system_monitor_stats.py", "--bar"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.ingest(text, false)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.statsStderr = String(text || "").trim().substring(0, 200)
    }
    onExited: function (code) { root.processExited(barProc, code) }
  }

  DeadlineProcess {
    id: fullProc
    deadlineMs: 9000
    environment: procEnv.env
    command: [root.py, root.binDir + "/system_monitor_stats.py"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.ingest(text, true)
    }
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.statsStderr = String(text || "").trim().substring(0, 200)
    }
    onExited: function (code) { root.processExited(fullProc, code) }
  }

  DeadlineProcess {
    id: fanSetProc
    deadlineMs: 6000
    environment: procEnv.env
    onExited: {
      helperStatusFile.reload()
      if (root.queuedFanArgs) {
        fanSetProc.command = root.queuedFanArgs
        root.queuedFanArgs = null
        fanSetProc.start()
      }
    }
  }

  DeadlineProcess {
    id: killProc
    deadlineMs: 5000
    environment: procEnv.env
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.killResult(text)
    }
  }

  // --- timers ------------------------------------------------------------------------------------

  // Bar: one cheap `--bar` run a minute while the bar is visible and the panel
  // is closed (the panel's own run feeds the bar while it is open). Backs off
  // on failure; revealed() refreshes once when the bar comes back.
  Timer {
    id: barTimer
    interval: Math.max(60000, freshness.nextDelayMs)
    running: gate.visible && !root.opened
    repeat: true
    onTriggered: root.refreshBar()
  }

  // Panel: full collect every 5 s only while the panel is open, plus once on open.
  Timer {
    id: fullTimer
    interval: freshness.nextDelayMs
    running: root.opened && gate.visible
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refreshFull()
  }

  Timer {
    id: disarmTimer
    interval: 5000
    onTriggered: root.armedKillPid = 0
  }

  Component.onCompleted: root.refreshBar()

  // Root-owned status from the packaged helper (version, mode, controllable).
  // Watched and re-read on every refresh; a read is spawn-free.
  FileView {
    id: helperStatusFile
    path: "/run/omarchy-fan/status.json"
    watchChanges: true
    printErrors: false
    onFileChanged: helperStatusFile.reload()
    onLoaded: root.readHelperStatus(true)
    onLoadFailed: root.readHelperStatus(false)
  }

  // Shell heartbeat for the helper: fixed presets expire when it is older than
  // 120 s, so the fans never stay pinned after the shell is gone. Written in
  // place (no process spawn) every 30 s, independent of panel visibility or
  // screen lock. The directory is created by omarchy-fan-set when a mode is
  // chosen; before that there is no preset to keep alive.
  readonly property string heartbeatPath: {
    var base = Quickshell.env("XDG_RUNTIME_DIR")
    return base ? base + "/omarchy-fan/heartbeat" : ""
  }

  FileView {
    id: heartbeatFile
    path: root.heartbeatPath
    preload: false
    watchChanges: false
    atomicWrites: true
    printErrors: false
  }

  Timer {
    id: heartbeatTimer
    interval: 30000
    running: root.heartbeatPath.length > 0 && root.fanControl
    repeat: true
    triggeredOnStart: true
    onTriggered: heartbeatFile.setText(String(Math.floor(Date.now() / 1000)))
  }

  // --- bar button -------------------------------------------------------------------------------

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰍛 " + root.memUsed + "G " + root.memPct + "% " + root.tempText(root.tempC) + " 󰈐 " + root.modeLetter()
    fontSize: Style.font.bodySmall
    active: root.memPct >= 80 || root.currentMode === "high" || root.tempC >= 70
    activeColor: root.memPct >= 85 || root.tempC >= 80 ? root.urgent : (root.bar ? root.bar.barForeground : Color.foreground)
    tooltipText: "RAM " + root.memUsed + "/" + root.memTotal + " GB"
                 + " · " + (root.tempSource === "cpu" ? "CPU " : (root.tempSource === "board" ? root.tempLabel + " " : "temp "))
                 + root.tempText(root.tempC)
                 + " · " + root.fanSummary()
                 + (root.fanControl ? " · right-click cycles fan mode" : "")
                 + " · middle-click btop"
    horizontalMargin: 4.0
    onPressed: function (buttonCode) {
      if (buttonCode === Qt.RightButton)
        root.cycleMode()
      else if (buttonCode === Qt.MiddleButton)
        root.btop()
      else
        root.toggle()
    }
  }

  // --- panel ------------------------------------------------------------------------------------

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(380), 460)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 780)
    Keys.onPressed: function (event) {
      if (event.key === Qt.Key_J || event.key === Qt.Key_Down) {
        root.selectedGroup = Math.min(root.groups.length - 1, root.selectedGroup + 1)
        root.armedKillPid = 0
        event.accepted = true
      } else if (event.key === Qt.Key_K || event.key === Qt.Key_Up) {
        root.selectedGroup = Math.max(0, root.selectedGroup - 1)
        root.armedKillPid = 0
        event.accepted = true
      } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
        root.toggleExpanded(root.selected())
        event.accepted = true
      } else if (event.key === Qt.Key_X) {
        root.requestKill(root.selected())
        event.accepted = true
      } else if (event.key === Qt.Key_B) {
        root.btop()
        event.accepted = true
      }
    }

    Flickable {
      id: flick
      anchors.fill: parent
      contentWidth: width
      contentHeight: mainColumn.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      flickableDirection: Flickable.VerticalFlick
      interactive: contentHeight > height

      Column {
        id: mainColumn
        width: flick.width
        spacing: Style.space(10)

        // Header: title, freshness, mode badge.
        RowLayout {
          width: parent.width
          spacing: Style.space(8)
          Text {
            textFormat: Text.PlainText
            text: "Resource & Fan"
            color: root.fg
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            font.bold: true
          }
          Text {
            visible: freshness.stale
            textFormat: Text.PlainText
            text: "stale · " + freshness.ageText
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
          Item { Layout.fillWidth: true }
          Rectangle {
            Layout.preferredWidth: modeLabel.implicitWidth + Style.space(14)
            Layout.preferredHeight: Style.space(22)
            radius: height / 2
            color: root.currentMode === "high" ? root.urgent : (root.currentMode === "auto" ? root.muted : root.accent)
            Text {
              id: modeLabel
              anchors.centerIn: parent
              textFormat: Text.PlainText
              text: root.fanControl ? (root.currentMode === "custom" ? root.customName.toUpperCase() : root.currentMode.toUpperCase()) : "READ ONLY"
              color: Color.background
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }
            MouseArea {
              anchors.fill: parent
              enabled: root.fanControl
              cursorShape: Qt.PointingHandCursor
              onClicked: root.cycleMode()
            }
          }
        }

        Text {
          visible: root.fetchError.length > 0
          width: parent.width
          textFormat: Text.PlainText
          text: root.fetchError
          color: root.urgent
          wrapMode: Text.Wrap
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        // ---------------- Overview ----------------
        PanelSeparator { foreground: root.fg }
        PanelSectionHeader {
          text: "OVERVIEW"
          foreground: root.fg
          fontFamily: root.fontFamily
        }

        // CPU
        Column {
          width: parent.width
          spacing: Style.space(4)
          RowLayout {
            width: parent.width
            Text {
              Layout.fillWidth: true
              textFormat: Text.PlainText
              text: root.cpuName
              elide: Text.ElideRight
              color: root.fg
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }
            Text {
              textFormat: Text.PlainText
              text: (root.hasFullData ? root.cpuLoad + "%" : "…") + "  ·  " + (root.cpuTemp >= 0 ? root.cpuTemp + "°C" : "no CPU sensor")
              color: root.levelColor(root.cpuLoad, 70, 90)
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }
          }
          Rectangle {
            width: parent.width
            height: Style.space(6)
            radius: height / 2
            color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.15)
            Rectangle {
              width: Math.max(height, parent.width * root.cpuLoad / 100.0)
              height: parent.height
              radius: height / 2
              color: root.levelColor(root.cpuLoad, 70, 90)
            }
          }
          Grid {
            visible: root.cpuCores.length > 0
            width: parent.width
            columns: Math.min(12, Math.max(1, root.cpuCores.length))
            columnSpacing: Style.space(3)
            rowSpacing: Style.space(3)
            Repeater {
              model: root.cpuCores
              delegate: Rectangle {
                required property var modelData
                width: (parent.width - parent.columnSpacing * (parent.columns - 1)) / parent.columns
                height: Style.space(14)
                radius: Style.space(2)
                color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.08)
                Rectangle {
                  anchors.bottom: parent.bottom
                  width: parent.width
                  height: parent.height * modelData.percent / 100.0
                  radius: parent.radius
                  color: root.levelColor(modelData.percent, 60, 85)
                  opacity: 0.6
                }
              }
            }
          }
        }

        // Memory
        Column {
          width: parent.width
          spacing: Style.space(4)
          RowLayout {
            width: parent.width
            Text {
              textFormat: Text.PlainText
              text: "Memory"
              color: root.fg
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }
            Item { Layout.fillWidth: true }
            Text {
              textFormat: Text.PlainText
              text: root.memUsed + " / " + root.memTotal + " GB  ·  " + root.memPct + "%"
              color: root.levelColor(root.memPct, 70, 85)
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }
          }
          Rectangle {
            width: parent.width
            height: Style.space(6)
            radius: height / 2
            color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.15)
            Rectangle {
              width: Math.max(height, parent.width * root.memPct / 100.0)
              height: parent.height
              radius: height / 2
              color: root.levelColor(root.memPct, 70, 85)
            }
          }
          Text {
            visible: root.hasFullData
            width: parent.width
            textFormat: Text.PlainText
            text: root.memAvail + " GB free · swap " + root.swapUsed + " / " + root.swapTotal + " GB" + (root.ramType ? " · " + root.ramType : "")
            elide: Text.ElideRight
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }

        // GPU
        Column {
          visible: root.gpuName.length > 0
          width: parent.width
          spacing: Style.space(4)
          RowLayout {
            width: parent.width
            Text {
              Layout.fillWidth: true
              textFormat: Text.PlainText
              text: root.gpuName
              elide: Text.ElideRight
              color: root.fg
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }
            Text {
              textFormat: Text.PlainText
              text: (root.gpuLoad >= 0 ? root.gpuLoad + "%" : "load n/a")
                    + (root.gpuTemp >= 0 ? "  ·  " + root.gpuTemp + "°C" : "")
                    + (root.gpuPowerW >= 0 ? "  ·  SoC " + root.gpuPowerW.toFixed(1) + " W" : "")
              color: root.levelColor(root.gpuLoad, 70, 90)
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }
          }
          Rectangle {
            visible: root.gpuLoad >= 0
            width: parent.width
            height: Style.space(6)
            radius: height / 2
            color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.15)
            Rectangle {
              width: Math.max(height, parent.width * root.gpuLoad / 100.0)
              height: parent.height
              radius: height / 2
              color: root.levelColor(root.gpuLoad, 70, 90)
            }
          }
          Text {
            visible: root.gpuLoad < 0 && root.gpuReason.length > 0
            width: parent.width
            textFormat: Text.PlainText
            text: root.gpuReason
            wrapMode: Text.Wrap
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
          Text {
            visible: root.gpuClients.length > 0
            width: parent.width
            textFormat: Text.PlainText
            text: "Using the GPU: " + root.gpuClients.join(", ")
            elide: Text.ElideRight
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }

        // Temperatures
        Column {
          visible: root.temps.length > 0
          width: parent.width
          spacing: Style.space(4)
          Text {
            textFormat: Text.PlainText
            text: root.cpuTemp >= 0 ? "Temperatures" : "Board temperatures (no CPU sensor exposed)"
            color: root.fg
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }
          Flow {
            width: parent.width
            spacing: Style.space(6)
            Repeater {
              model: root.temps
              delegate: Rectangle {
                required property var modelData
                width: tempChip.implicitWidth + Style.space(12)
                height: tempChip.implicitHeight + Style.space(6)
                radius: height / 2
                color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.08)
                Text {
                  id: tempChip
                  anchors.centerIn: parent
                  textFormat: Text.PlainText
                  text: modelData.label + "  " + modelData.c + "°"
                  color: root.levelColor(modelData.c, 65, 85)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
            }
          }
        }

        // Storage
        Column {
          visible: root.disks.length > 0
          width: parent.width
          spacing: Style.space(4)
          Repeater {
            model: root.disks
            delegate: Column {
              required property var modelData
              width: parent.width
              spacing: Style.space(2)
              RowLayout {
                width: parent.width
                Text {
                  Layout.fillWidth: true
                  textFormat: Text.PlainText
                  text: "Disk " + modelData.mount
                  elide: Text.ElideMiddle
                  color: root.fg
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }
                Text {
                  textFormat: Text.PlainText
                  text: modelData.used.toFixed(0) + " / " + modelData.total.toFixed(0) + " GB  ·  " + modelData.percent + "%"
                    + (modelData.mount === "/" && root.nvmeTemp >= 0 ? "  ·  " + root.nvmeTemp + "°C" : "")
                  color: root.levelColor(modelData.percent, 80, 95)
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
              Rectangle {
                width: parent.width
                height: Style.space(4)
                radius: height / 2
                color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.15)
                Rectangle {
                  width: Math.max(height, parent.width * modelData.percent / 100.0)
                  height: parent.height
                  radius: height / 2
                  color: root.levelColor(modelData.percent, 80, 95)
                }
              }
            }
          }
        }

        // ---------------- Fans ----------------
        PanelSeparator { foreground: root.fg }
        PanelSectionHeader {
          text: "FANS"
          foreground: root.fg
          fontFamily: root.fontFamily
        }

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.fanSummary()
          wrapMode: Text.Wrap
          color: root.fg
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
        }
        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.helperHint()
          wrapMode: Text.Wrap
          color: root.fanControl ? root.dim : root.accent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
        Rectangle {
          visible: !root.fanControl && root.helperState !== "missing" && root.currentMode !== "auto"
          width: parent.width
          height: Style.space(30)
          radius: Style.cornerRadius
          color: "transparent"
          border.color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.4)
          border.width: 1
          Text {
            anchors.centerIn: parent
            textFormat: Text.PlainText
            text: "Reset to auto"
            color: root.fg
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }
          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.setMode("auto")
          }
        }
        Row {
          width: parent.width
          spacing: Style.space(6)
          visible: root.fanControl
          Repeater {
            model: ["auto", "low", "med", "high", "custom"]
            delegate: Rectangle {
              required property string modelData
              width: (parent.width - Style.space(24)) / 5
              height: Style.space(30)
              radius: Style.cornerRadius
              color: root.currentMode === modelData ? root.fg : "transparent"
              border.color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.4)
              border.width: 1
              Text {
                anchors.centerIn: parent
                textFormat: Text.PlainText
                text: modelData === "med" ? "Med" : modelData.charAt(0).toUpperCase() + modelData.slice(1)
                color: root.currentMode === modelData ? Color.background : root.fg
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.setMode(modelData)
              }
            }
          }
        }
        Row {
          visible: root.fanControl && root.currentMode === "custom"
          width: parent.width
          spacing: Style.space(6)
          Repeater {
            model: ["silent", "balanced", "performance"]
            delegate: Rectangle {
              required property string modelData
              width: (parent.width - Style.space(12)) / 3
              height: Style.space(26)
              radius: Style.cornerRadius
              color: root.customName === modelData ? root.accent : "transparent"
              border.color: Qt.rgba(root.fg.r, root.fg.g, root.fg.b, 0.4)
              border.width: 1
              Text {
                anchors.centerIn: parent
                textFormat: Text.PlainText
                text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                color: root.customName === modelData ? Color.background : root.fg
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.setCustom(modelData)
              }
            }
          }
        }
        // Read-only preview of the active custom curve (temperature → PWM).
        Canvas {
          id: curveCanvas
          visible: root.fanControl && root.currentMode === "custom" && root.fanCurve.length > 1
          width: parent.width
          height: Style.space(60)
          onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var pts = root.fanCurve
            if (!pts || pts.length < 2)
              return
            var pad = 6
            var cw = width - pad * 2
            var ch = height - pad * 2
            ctx.strokeStyle = "rgba(" + Math.round(root.fg.r * 255) + "," + Math.round(root.fg.g * 255) + "," + Math.round(root.fg.b * 255) + ",0.15)"
            ctx.lineWidth = 1
            ctx.beginPath()
            ctx.moveTo(pad, pad)
            ctx.lineTo(pad, height - pad)
            ctx.lineTo(width - pad, height - pad)
            ctx.stroke()
            ctx.strokeStyle = root.accent
            ctx.lineWidth = 2
            ctx.beginPath()
            for (var i = 0; i < pts.length; i++) {
              var x = pad + (Number(pts[i][0]) / 100) * cw
              var y = (height - pad) - (Number(pts[i][1]) / 255) * ch
              if (i === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            }
            ctx.stroke()
          }
          Connections {
            target: root
            function onFanCurveChanged() {
              if (curveCanvas.visible)
                curveCanvas.requestPaint()
            }
          }
        }

        // ---------------- What's running ----------------
        PanelSeparator { foreground: root.fg }
        RowLayout {
          width: parent.width
          PanelSectionHeader {
            text: "WHAT'S RUNNING"
            foreground: root.fg
            fontFamily: root.fontFamily
          }
          Item { Layout.fillWidth: true }
          Text {
            textFormat: Text.PlainText
            text: "busy first, then memory · j/k ↵ x · b btop"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
        Text {
          visible: root.hasFullData && !root.warm
          width: parent.width
          textFormat: Text.PlainText
          text: "Measuring CPU use; numbers appear on the next refresh."
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
        Text {
          visible: !root.hasFullData
          width: parent.width
          textFormat: Text.PlainText
          text: "Reading processes…"
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        Column {
          width: parent.width
          spacing: Style.space(2)
          Repeater {
            model: root.groups
            delegate: Rectangle {
              id: groupRow
              required property var modelData
              required property int index
              readonly property bool expanded: root.expandedLabel === modelData.label
              readonly property bool armed: modelData.killPid > 1 && root.armedKillPid === modelData.killPid
              width: parent.width
              height: rowContent.implicitHeight + Style.space(8)
              radius: Style.cornerRadius
              color: index === root.selectedGroup ? Style.selectedFillFor(root.fg, Color.accent) : "transparent"

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onEntered: root.selectedGroup = groupRow.index
                onClicked: root.toggleExpanded(groupRow.modelData)
              }

              Column {
                id: rowContent
                x: Style.space(6)
                y: Style.space(4)
                width: parent.width - Style.space(12)
                spacing: Style.space(2)

                RowLayout {
                  width: parent.width
                  spacing: Style.space(8)
                  Text {
                    Layout.preferredWidth: Style.space(18)
                    textFormat: Text.PlainText
                    text: root.kindGlyph(groupRow.modelData.kind)
                    color: groupRow.modelData.kind === "agent" ? root.accent : root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                  }
                  Column {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                      width: parent.width
                      textFormat: Text.PlainText
                      text: groupRow.modelData.label + (groupRow.modelData.count > 1 ? "  ×" + groupRow.modelData.count : "")
                      elide: Text.ElideRight
                      color: root.fg
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }
                    Text {
                      width: parent.width
                      textFormat: Text.PlainText
                      text: groupRow.modelData.detail
                      elide: Text.ElideRight
                      color: root.dim
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                    }
                  }
                  Column {
                    spacing: 0
                    Text {
                      anchors.right: parent.right
                      textFormat: Text.PlainText
                      text: groupRow.modelData.cpu.toFixed(groupRow.modelData.cpu >= 10 ? 0 : 1) + "% CPU"
                      color: root.levelColor(groupRow.modelData.cpu, 50, 100)
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      font.bold: groupRow.modelData.cpu >= 1
                    }
                    Text {
                      anchors.right: parent.right
                      textFormat: Text.PlainText
                      text: root.memText(groupRow.modelData.mem)
                      color: root.dim
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                    }
                  }
                }

                RowLayout {
                  visible: groupRow.expanded
                  width: parent.width
                  spacing: Style.space(8)
                  Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: Style.space(26)
                    textFormat: Text.PlainText
                    text: (groupRow.modelData.count > 1 ? "Top PIDs " : "PID ") + groupRow.modelData.pids.join(", ")
                          + (groupRow.modelData.count > groupRow.modelData.pids.length ? " …" : "")
                          + (groupRow.modelData.killPid > 1 ? "" : "  ·  stop it from its app")
                    elide: Text.ElideRight
                    color: root.dim
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                  }
                  Rectangle {
                    visible: groupRow.modelData.killPid > 1
                    Layout.preferredWidth: killText.implicitWidth + Style.space(14)
                    Layout.preferredHeight: killText.implicitHeight + Style.space(6)
                    radius: Style.cornerRadius
                    color: groupRow.armed ? root.urgent : "transparent"
                    border.color: root.urgent
                    border.width: 1
                    Text {
                      id: killText
                      anchors.centerIn: parent
                      textFormat: Text.PlainText
                      text: groupRow.armed ? "Confirm kill" : "Kill"
                      color: groupRow.armed ? Color.background : root.urgent
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                      font.bold: true
                    }
                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.requestKill(groupRow.modelData)
                    }
                  }
                }
              }
            }
          }
        }

        Text {
          visible: root.killStatus.length > 0
          width: parent.width
          textFormat: Text.PlainText
          text: root.killStatus
          elide: Text.ElideRight
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
      }
    }
  }
}
