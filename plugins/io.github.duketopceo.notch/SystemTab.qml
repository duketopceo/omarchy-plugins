import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "System.js" as Sys

// System tab: rings for CPU (P/E clusters), GPU, RAM and the Neural Engine,
// 60 s sparklines (CPU, GPU, temp, power), temps, fans with a mode control,
// ANE status and MLX serve status. Everything is sampled every 2 s and ONLY
// while the tab is visible. Reads are sysfs/procfs through FileView plus one
// grep spawn for hwmon/cpufreq; no root needed. GPU shows n/a: the Asahi AGX
// driver exposes no utilization counter outside debugfs (root-only).
Item {
  id: tab

  property var notch: null
  readonly property color textColor: notch ? notch.textColor : Commons.Color.foreground
  readonly property color dimColor: notch ? notch.dimColor : Commons.Color.muted
  readonly property string family: notch ? notch.fontFamily : Commons.Style.font.family
  readonly property string home: Quickshell.env("HOME")
  readonly property bool active: visible

  readonly property color cpuTone: "#6fa8ff"
  readonly property color gpuTone: "#b58cff"
  readonly property color ramTone: "#6fbf73"
  readonly property color aneTone: "#e0b050"
  readonly property color tempTone: "#e07a5f"
  readonly property color powerTone: "#5fc9c9"

  // ---- state
  property var prevStat: null
  property var curStat: null
  property var clusters: ({ e: null, p: null })
  property var mem: Sys.parseMeminfo("")
  property var hw: Sys.parseHwmon("")
  property var helper: Sys.parseFanHelper("")
  property var aneStats: Sys.parseAneStats("")
  property var prevAne: null
  property real prevAneAt: 0
  property var aneCheck: Sys.parseAneCheck("")
  property var scan: ({ anePids: [], aneProcs: [], mlx: [], mlxPorts: [] })
  property string aneRt: ""
  property var aneJobs: []
  property real aneLastUsed: 0
  property var mlxModels: []
  property real nowMs: Date.now()
  property var resv: Sys.parseReservations("")
  property string pendingMode: ""
  property real pendingUntil: 0
  property bool copied: false
  property int tick: 0

  property real cpuAll: -1
  property real cpuP: -1
  property real cpuE: -1
  property real aneBusy: -1
  property var hCpu: []
  property var hGpu: []
  property var hTemp: []
  property var hPower: []

  readonly property string fanSet: home + "/.config/omarchy/plugins/lukedaduke.fan/bin/omarchy-fan-set"
  readonly property string shownMode: pendingMode !== "" ? pendingMode : helper.mode
  readonly property bool canSetMode: helper.present && helper.controllable

  function sample() {
    var now = Date.now()
    var s = Sys.parseCpuStat(statFile.text())
    prevStat = curStat
    curStat = s
    cpuAll = orNeg(Sys.cpuUsage(prevStat, curStat, null))
    cpuP = clusters.p ? orNeg(Sys.cpuUsage(prevStat, curStat, clusters.p.cpus)) : -1
    cpuE = clusters.e ? orNeg(Sys.cpuUsage(prevStat, curStat, clusters.e.cpus)) : -1
    mem = Sys.parseMeminfo(memFile.text())
    var a = Sys.parseAneStats(aneFile.text())
    var u = Sys.aneUtil(prevAne, a, now - prevAneAt)
    nowMs = now
    aneRt = rtFile.text()
    if (a.ok) {
      aneLastUsed = Sys.aneLastUsed(prevAne && prevAne.ok ? prevAne.jobs : null, a.jobs, now, aneLastUsed)
      aneJobs = Sys.pushJobs(aneJobs, now, a.jobs, 60000)
    }
    aneBusy = orNeg(u)
    prevAne = a
    prevAneAt = now
    aneStats = a
    helper = Sys.parseFanHelper(helperFile.text())
    if (pendingMode !== "" && (helper.mode === pendingMode || now > pendingUntil)) pendingMode = ""
    hCpu = Sys.pushSample(hCpu, cpuAll >= 0 ? cpuAll : null)
    hGpu = Sys.pushSample(hGpu, null)
    hTemp = Sys.pushSample(hTemp, hw.hottest ? hw.hottest.c : null)
    var pw = Sys.totalPower(hw.powers)
    hPower = Sys.pushSample(hPower, pw)
    if (!hwProc.running) hwProc.running = true
    if (tick % 3 === 0 && !scanProc.running) scanProc.running = true
    if (tick % 30 === 0 && !checkProc.running) checkProc.running = true
    if (tick % 15 === 0) resvFile.reload()
    tick++
  }
  function orNeg(v) { return v === null || v === undefined ? -1 : v }

  function refreshFiles() {
    statFile.reload(); memFile.reload(); aneFile.reload(); rtFile.reload(); helperFile.reload()
  }
  function poll() { refreshFiles(); sampleLater.restart() }
  Timer { id: sampleLater; interval: 60; onTriggered: tab.sample() }

  Timer {
    interval: Sys.SAMPLE_MS
    repeat: true
    running: tab.active
    triggeredOnStart: true
    onTriggered: tab.poll()
  }
  onActiveChanged: if (active) { tick = 0; prevStat = null; prevAne = null }

  function setMode(id) {
    var arg = Sys.fanModeArg(id)
    if (!arg || !canSetMode) return
    pendingMode = arg
    pendingUntil = Date.now() + 6000
    Quickshell.execDetached(["/usr/bin/python3", fanSet, arg])
  }
  function copyMlx() {
    Quickshell.execDetached(["/usr/bin/wl-copy", Sys.MLX_COMMAND])
    copied = true
    copiedTimer.restart()
  }
  Timer { id: copiedTimer; interval: 1500; onTriggered: tab.copied = false }

  // ---- sources
  FileView { id: statFile; path: "/proc/stat"; watchChanges: false; printErrors: false }
  FileView { id: memFile; path: "/proc/meminfo"; watchChanges: false; printErrors: false }
  FileView { id: rtFile; path: "/sys/class/accel/accel0/device/power/runtime_status"; watchChanges: false; printErrors: false }
  FileView { id: aneFile; path: "/sys/class/accel/accel0/device/ane_stats"; watchChanges: false; printErrors: false }
  FileView { id: helperFile; path: "/run/omarchy-fan/status.json"; watchChanges: false; printErrors: false }
  FileView {
    id: resvFile
    path: tab.home + "/.local/share/mlx-omarchy/reservations.json"
    watchChanges: false
    printErrors: false
    onLoaded: tab.resv = Sys.parseReservations(text())
    onLoadFailed: tab.resv = Sys.parseReservations("")
  }

  Process {
    id: hwProc
    command: ["/usr/bin/sh", "-c", "exec /usr/bin/grep -H . /sys/class/hwmon/hwmon*/name /sys/class/hwmon/hwmon*/temp*_input /sys/class/hwmon/hwmon*/temp*_label /sys/class/hwmon/hwmon*/fan*_input /sys/class/hwmon/hwmon*/fan*_label /sys/class/hwmon/hwmon*/fan*_target /sys/class/hwmon/hwmon*/fan*_min /sys/class/hwmon/hwmon*/fan*_max /sys/class/hwmon/hwmon*/power*_input /sys/class/hwmon/hwmon*/power*_label /sys/devices/system/cpu/cpufreq/policy*/related_cpus /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq 2>/dev/null"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (!text || text.length > 200000) return
        tab.hw = Sys.parseHwmon(text)
        tab.clusters = Sys.buildClusters(Sys.parsePolicies(text))
      }
    }
  }

  Process {
    id: scanProc
    command: ["/usr/bin/sh", "-c", "echo ==ane; /usr/bin/fuser /dev/accel/accel0 2>/dev/null; echo ==comm; for p in $(/usr/bin/fuser /dev/accel/accel0 2>/dev/null); do echo \"$p $(/usr/bin/cat /proc/$p/comm 2>/dev/null)\"; done; echo ==ss; /usr/bin/ss -ltnp 2>/dev/null; echo ==mlx; /usr/bin/pgrep -af '[m]lx' 2>/dev/null"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (text.length >= 100000) return
        tab.scan = Sys.parseScan(text)
        var cmd = Sys.modelsCommand(tab.scan.mlxPorts)
        if (cmd === "") tab.mlxModels = []
        else if (!modelsProc.running) { modelsProc.command = ["/usr/bin/sh", "-c", cmd]; modelsProc.running = true }
      }
    }
  }

  Process {
    id: modelsProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.length < 200000) tab.mlxModels = Sys.parseModelIds(text)
    }
  }

  Process {
    id: checkProc
    command: ["/usr/bin/omarchy-ane-check"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: if (text.length < 100000) tab.aneCheck = Sys.parseAneCheck(text)
    }
  }

  // ---- layout (content area is about 428 x 164)
  readonly property int leftW: 250

  function pct(v) { return v >= 0 ? Math.round(v) + "%" : "n/a" }

  Row {
    id: rings
    anchors.left: parent.left
    anchors.top: parent.top
    spacing: 0

    // CPU
    Column {
      width: 62; spacing: 1
      SystemRing {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 46; height: 46
        value: tab.cpuAll / 100; tone: tab.cpuTone
        text: tab.pct(tab.cpuAll); family: tab.family; textColor: tab.textColor
      }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "CPU"; color: tab.textColor; font.family: tab.family; font.pixelSize: 11; font.weight: Font.DemiBold }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "P" + (tab.cpuP >= 0 ? Math.round(tab.cpuP) : "-") + " E" + (tab.cpuE >= 0 ? Math.round(tab.cpuE) : "-"); color: tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: tab.clusters.p ? Sys.fmtGHz(tab.clusters.p.khz) : "--"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
    }
    // GPU
    Column {
      width: 62; spacing: 1
      SystemRing {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 46; height: 46
        value: -1; tone: tab.gpuTone
        text: "n/a"; family: tab.family; textColor: tab.dimColor
      }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "GPU"; color: tab.textColor; font.family: tab.family; font.pixelSize: 11; font.weight: Font.DemiBold }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "32-core AGX"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "needs root"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
    }
    // RAM
    Column {
      width: 62; spacing: 1
      SystemRing {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 46; height: 46
        value: tab.mem.pct / 100; tone: tab.ramTone
        text: tab.mem.ok ? tab.mem.pct + "%" : "n/a"; family: tab.family; textColor: tab.textColor
      }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "RAM"; color: tab.textColor; font.family: tab.family; font.pixelSize: 11; font.weight: Font.DemiBold }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: Sys.fmtGiB(tab.mem.usedKb) + " / " + Sys.fmtGiB(tab.mem.totalKb).replace(" GB", ""); color: tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "zram " + Sys.fmtGiB(tab.mem.swapUsedKb); color: tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
    }
    // ANE
    Column {
      width: 62; spacing: 1
      SystemRing {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 46; height: 46
        value: tab.aneBusy / 100; tone: tab.aneTone
        text: tab.aneStats.ok ? tab.pct(tab.aneBusy) : "n/a"; family: tab.family; textColor: tab.textColor
      }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: "ANE"; color: tab.textColor; font.family: tab.family; font.pixelSize: 11; font.weight: Font.DemiBold }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: tab.aneCheck.state; color: tab.aneCheck.ready ? "#6fbf73" : tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
      Text { textFormat: Text.PlainText; anchors.horizontalCenter: parent.horizontalCenter; text: tab.aneStats.ok ? tab.aneStats.jobs + " jobs" : "--"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 9 }
    }
  }

  // Sparklines
  Row {
    id: sparks
    anchors.left: parent.left
    anchors.top: rings.bottom
    anchors.topMargin: 5
    spacing: 4
    SystemSpark { width: 59; height: 32; values: tab.hCpu; tone: tab.cpuTone; label: "CPU"; readout: tab.pct(tab.cpuAll); family: tab.family; textColor: tab.textColor; dimColor: tab.dimColor }
    SystemSpark { width: 59; height: 32; values: tab.hGpu; tone: tab.gpuTone; label: "GPU"; emptyText: "n/a"; family: tab.family; textColor: tab.textColor; dimColor: tab.dimColor }
    SystemSpark {
      width: 59; height: 32; values: tab.hTemp; tone: tab.tempTone; label: "TEMP"
      minValue: 20; maxValue: 90
      readout: tab.hw.hottest ? Math.round(tab.hw.hottest.c) + "°" : ""
      family: tab.family; textColor: tab.textColor; dimColor: tab.dimColor
    }
    SystemSpark {
      width: 59; height: 32; values: tab.hPower; tone: tab.powerTone; label: "PWR"
      minValue: 0; maxValue: 100
      readout: Sys.totalPower(tab.hw.powers) !== null ? Math.round(Sys.totalPower(tab.hw.powers)) + " W" : ""
      family: tab.family; textColor: tab.textColor; dimColor: tab.dimColor
    }
  }

  // ANE + MLX status lines
  Column {
    anchors.left: parent.left
    anchors.top: sparks.bottom
    anchors.topMargin: 5
    width: tab.leftW - 4
    spacing: 3
    Text {
      textFormat: Text.PlainText
      width: parent.width; elide: Text.ElideRight
      color: tab.aneRt.trim() === "active" ? "#6fbf73" : tab.dimColor; font.family: tab.family; font.pixelSize: 10
      text: "ANE " + Sys.aneState(tab.aneRt) + (tab.aneCheck.version !== "" ? " v" + tab.aneCheck.version : "") + " · " + (Sys.jobsPerMin(tab.aneJobs) !== null ? Sys.jobsPerMin(tab.aneJobs) + " jobs/min" : "-- jobs/min") + " · used " + Sys.fmtAgo(tab.aneLastUsed, tab.nowMs)
    }
    Text {
      textFormat: Text.PlainText
      width: parent.width; elide: Text.ElideRight
      color: tab.dimColor; font.family: tab.family; font.pixelSize: 10
      text: "ANE users: " + (tab.scan.aneProcs.length > 0 ? tab.scan.aneProcs.join(", ") : "none open")
    }
    Item {
      width: parent.width; height: 14
      Text {
        textFormat: Text.PlainText
        anchors.left: parent.left
        anchors.right: copyBtn.left
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        elide: Text.ElideRight
        color: tab.scan.mlx.length > 0 ? "#6fbf73" : tab.dimColor
        font.family: tab.family; font.pixelSize: 10
        text: (tab.scan.mlx.length > 0 ? "MLX x" + tab.scan.mlx.length + " " + (tab.mlxModels.length > 0 ? tab.mlxModels.join(", ") : (tab.scan.mlx[0].model || "serving") + " :" + tab.scan.mlx[0].port) : "MLX not running") + (tab.resv.count > 0 ? " · rsv " + tab.resv.gib + "G" : "")
      }
      Rectangle {
        id: copyBtn
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 54; height: 14; radius: 7
        color: copyHit.containsMouse ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.08)
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: tab.copied ? "copied" : "copy cmd"
          color: tab.copied ? "#6fbf73" : tab.textColor
          font.family: tab.family; font.pixelSize: 9
        }
        MouseArea { id: copyHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tab.copyMlx() }
      }
    }
  }

  // ---- right column: temps, fans, mode
  Column {
    id: rightCol
    anchors.right: parent.right
    anchors.top: parent.top
    width: parent.width - tab.leftW - 12
    spacing: 2

    Text { textFormat: Text.PlainText; text: "Temps"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 9; font.weight: Font.DemiBold }
    Repeater {
      model: tab.hw.temps.slice(0, 4)
      delegate: Item {
        required property var modelData
        width: rightCol.width; height: 13
        Text { textFormat: Text.PlainText; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: modelData.name; color: tab.textColor; font.family: tab.family; font.pixelSize: 10 }
        Rectangle {
          anchors.verticalCenter: parent.verticalCenter
          x: 58; height: 3; radius: 1.5
          width: Math.max(2, (rightCol.width - 58 - 34) * Math.max(0, Math.min(1, (modelData.c - 20) / 70)))
          color: modelData.c >= 70 ? "#e07a5f" : modelData.c >= 55 ? "#e0b050" : "#6fbf73"
        }
        Text { textFormat: Text.PlainText; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: Math.round(modelData.c) + "°C"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 10 }
      }
    }
    Text { visible: !tab.hw.ok || tab.hw.temps.length === 0; textFormat: Text.PlainText; text: "no sensors"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 10 }

    Item { width: 1; height: 3 }
    Text { textFormat: Text.PlainText; text: "Fans · " + Sys.fanModeTitle(tab.shownMode); color: tab.dimColor; font.family: tab.family; font.pixelSize: 9; font.weight: Font.DemiBold }
    Repeater {
      model: tab.hw.fans.slice(0, 2)
      delegate: Item {
        required property var modelData
        width: rightCol.width; height: 13
        Text { textFormat: Text.PlainText; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; text: "F" + modelData.id.replace("fan", ""); color: tab.textColor; font.family: tab.family; font.pixelSize: 10 }
        Rectangle {
          anchors.verticalCenter: parent.verticalCenter
          x: 22; height: 3; radius: 1.5
          width: Math.max(2, (rightCol.width - 22 - 74) * Sys.fanFraction(modelData))
          color: "#6fa8ff"
        }
        Text {
          textFormat: Text.PlainText
          anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
          text: Sys.fmtRpm(modelData.rpm) + (modelData.target !== null && modelData.target > 0 ? " →" + modelData.target : "")
          color: tab.dimColor; font.family: tab.family; font.pixelSize: 10
        }
      }
    }
    Text { visible: tab.hw.fans.length === 0; textFormat: Text.PlainText; text: "no fans"; color: tab.dimColor; font.family: tab.family; font.pixelSize: 10 }

    Row {
      spacing: 3
      Repeater {
        model: Sys.FAN_MODES.filter(function (m) { return m.id !== "med" })
        delegate: Rectangle {
          required property var modelData
          readonly property bool sel: tab.shownMode === modelData.id
          width: Math.floor((rightCol.width - 6) / 3); height: 17; radius: 8.5
          opacity: tab.canSetMode ? 1 : 0.45
          color: sel ? Qt.rgba(0.44, 0.66, 1, 0.30) : (pillHit.containsMouse && tab.canSetMode ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.08))
          Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: modelData.title; color: tab.textColor; font.family: tab.family; font.pixelSize: 10 }
          MouseArea { id: pillHit; anchors.fill: parent; hoverEnabled: true; enabled: tab.canSetMode; cursorShape: Qt.PointingHandCursor; onClicked: tab.setMode(modelData.id) }
        }
      }
    }
  }
}
