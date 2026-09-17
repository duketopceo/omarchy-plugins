import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.duketopceo.bumblebee"
  ipcTarget: "io.github.duketopceo.bumblebee"

  // ---- payload state (emitted by bin/scan_bumblebee.py) ----
  property bool installed: false
  property int ageS: -1
  property int exposureCount: 0
  property var exposures: []
  property int catalogEntries: 0
  property var catalogNames: []
  property var scanLog: []
  property bool partial: false
  property string lastError: ""
  property bool isRefreshing: false
  property string currentTab: "exposures" // "exposures" | "catalog" | "log"

  // ---- palette: fg/dim + alpha fills only, never a raw hex ----
  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(fg, 1.5)
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  // State color: dim until installed, urgent on any exposure, accent when clean.
  readonly property color stateColor: !installed ? dim
                                     : (exposureCount > 0 ? urgent : accent)

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

  function fgFill(alpha) {
    var rgb = _rgb(fg)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

  function stateFill(alpha) {
    var rgb = _rgb(stateColor)
    return Qt.rgba(rgb[0], rgb[1], rgb[2], alpha)
  }

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

  function refresh() { startScan([]) }
  // Rescan button: --force tells the helper to ignore cache freshness.
  function forceRefresh() { startScan(["--force"]) }

  function startScan(args) {
    if (!statusProc.running) {
      statusProc.command = [root.py, root.pluginRoot + "/bin/scan_bumblebee.py"].concat(args)
      isRefreshing = true
      statusProc.running = true
      statusDeadline.restart()
    }
  }

  function fmtAge(ageS) {
    if (ageS < 0) return "never"
    if (ageS < 90) return ageS + "s"
    if (ageS < 5400) return Math.round(ageS / 60) + "m"
    if (ageS < 129600) return Math.round(ageS / 3600) + "h"
    return Math.round(ageS / 86400) + "d"
  }

  function relTime(iso) {
    var t = Date.parse(String(iso || ""))
    if (!isFinite(t)) return ""
    return fmtAge(Math.max(0, Math.round((Date.now() - t) / 1000))) + " ago"
  }

  function sevUrgent(sev) {
    var s = String(sev || "").toLowerCase()
    return s === "critical" || s === "high"
  }

  function exposureSub(e) {
    if (!e) return ""
    var parts = []
    if (e.ecosystem) parts.push(String(e.ecosystem))
    var pv = e.package ? String(e.package) : ""
    if (e.version) pv += (pv.length ? "@" : "") + String(e.version)
    if (pv.length) parts.push(pv)
    return parts.join(" · ")
  }

  function statusPillText() {
    if (!installed) return "SETUP"
    if (exposureCount <= 0) return "CLEAN"
    return (exposureCount > 99 ? "99+" : String(exposureCount)) + " EXPOSED"
  }

  function subtitleText() {
    var s = "supply-chain exposure radar"
    if (installed && ageS >= 0) s += " · " + fmtAge(ageS) + " ago"
    if (installed && partial) s += " · partial"
    return s
  }

  function logStatusColor(status) {
    var s = String(status || "")
    if (s === "complete") return accent
    if (s === "error") return urgent
    return dim
  }

  function logMeta(e) {
    if (!e) return ""
    var parts = []
    var rel = relTime(e.scanned_at)
    if (rel !== "") parts.push(rel)
    var ms = Number(e.duration_ms)
    if (isFinite(ms) && ms >= 0) parts.push(Math.round(ms) + "ms")
    return parts.join(" · ")
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: statusProc
    command: [root.py, root.pluginRoot + "/bin/scan_bumblebee.py"]
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
          if (!data || typeof data !== "object") return
          root.installed = data.installed === true
          root.ageS = (typeof data.age_s === "number" && isFinite(data.age_s))
                      ? Math.max(0, Math.round(data.age_s)) : -1
          root.exposureCount = (typeof data.exposure_count === "number" && data.exposure_count > 0)
                               ? Math.round(data.exposure_count) : 0
          root.exposures = (Array.isArray(data.exposures) ? data.exposures : []).slice(0, 50)
          root.catalogEntries = (typeof data.catalog_entries === "number" && data.catalog_entries > 0)
                                ? Math.round(data.catalog_entries) : 0
          root.catalogNames = (Array.isArray(data.catalog_names) ? data.catalog_names : []).slice(0, 12)
          root.scanLog = (Array.isArray(data.log) ? data.log : []).slice(0, 20)
          root.partial = data.partial === true
          root.lastError = typeof data.error === "string" ? data.error : ""
        } catch (e) {}
      }
    }
    onExited: {
      statusDeadline.stop()
      root.isRefreshing = false
    }
  }

  // Hard whole-job deadline. scan_bumblebee.py calls os.setsid() and keeps
  // helpers in its own session group, so a group-kill reaps the whole tree.
  // Helper's own backstop is JOB_DEADLINE_S=30s; give the watchdog slack
  // above it so a cold baseline scan can publish its cache first.
  Timer {
    id: statusDeadline
    interval: 35000
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
    interval: 60000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // Refresh on any open path — bar click below, IPC/keyboard summon here.
  onOpenedChanged: if (opened) root.refresh()

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰒃"
    tooltipText: "Bumblebee · Supply Chain"
    dimmed: !root.installed
    active: root.installed && root.exposureCount > 0
    foreground: root.installed && root.exposureCount === 0
                ? root.accent
                : (root.bar ? root.bar.barForeground : Color.foreground)
    onPressed: function (b) {
      root.refresh()
      root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Style.space(500), 500)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 640)

    Column {
      id: mainColumn
      width: parent.width
      spacing: Style.space(10)

      // ---- header ----
      Row {
        width: parent.width
        spacing: Style.space(8)

        Rectangle {
          width: Style.space(36)
          height: Style.space(36)
          radius: Style.cornerRadius
          color: root.accentFill(0.14)
          border.color: root.accentFill(0.35)
          anchors.verticalCenter: parent.verticalCenter

          Text {
            anchors.centerIn: parent
            text: "󰒃"
            textFormat: Text.PlainText
            color: root.accent
            font.pixelSize: Style.space(20)
          }
        }

        Column {
          width: parent.width - Style.space(36) - statusPill.width - rescanBtn.width
                 - parent.spacing * 3
          spacing: Style.space(2)
          anchors.verticalCenter: parent.verticalCenter

          Text {
            width: parent.width
            text: "Bumblebee"
            textFormat: Text.PlainText
            color: root.fg
            font.family: root.fontFamily
            font.pixelSize: Style.font.subtitle
            font.bold: true
            elide: Text.ElideRight
          }
          Text {
            width: parent.width
            text: root.subtitleText()
            textFormat: Text.PlainText
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        // Status pill: SETUP (dim) / CLEAN (accent) / N EXPOSED (urgent)
        Rectangle {
          id: statusPill
          height: Style.space(24)
          width: statusPillText.implicitWidth + Style.space(16)
          radius: Style.cornerRadius
          color: root.stateFill(0.12)
          border.color: root.stateFill(0.45)
          anchors.verticalCenter: parent.verticalCenter

          Text {
            id: statusPillText
            anchors.centerIn: parent
            text: root.statusPillText()
            textFormat: Text.PlainText
            color: root.stateColor
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            font.bold: true
          }
        }

        // Force a fresh scan (helper --force bypasses cache freshness)
        Rectangle {
          id: rescanBtn
          height: Style.space(24)
          width: rescanText.implicitWidth + Style.space(14)
          radius: Style.cornerRadius
          color: mRescan.containsMouse ? root.accentFill(0.12) : "transparent"
          border.color: root.accentFill(0.5)
          opacity: root.isRefreshing ? 0.6 : 1.0
          anchors.verticalCenter: parent.verticalCenter

          Text {
            id: rescanText
            anchors.centerIn: parent
            text: root.isRefreshing ? "Scanning" : "Rescan"
            textFormat: Text.PlainText
            color: root.fg
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }

          MouseArea {
            id: mRescan
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            enabled: !root.isRefreshing
            onClicked: root.forceRefresh()
          }
        }
      }

      // ---- tab bar ----
      Row {
        width: parent.width
        spacing: Style.space(6)

        Repeater {
          model: ["exposures", "catalog", "log"]

          delegate: Rectangle {
            required property string modelData
            height: Style.space(28)
            width: tabLabel.implicitWidth + Style.space(16)
            radius: Style.cornerRadius
            color: root.currentTab === modelData
              ? root.accentFill(0.12)
              : (tabMouse.containsMouse ? root.accentFill(0.06) : "transparent")
            border.color: root.currentTab === modelData
              ? root.accentFill(0.45)
              : "transparent"

            Text {
              id: tabLabel
              anchors.centerIn: parent
              text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
              textFormat: Text.PlainText
              color: root.currentTab === modelData ? root.fg : root.dim
              font.bold: root.currentTab === modelData
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }

            MouseArea {
              id: tabMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.currentTab = modelData
            }
          }
        }
      }

      PanelSeparator { foreground: root.fg }

      // ---- error / setup states ----
      Column {
        visible: root.lastError !== "" || !root.installed
        width: parent.width
        spacing: Style.space(6)

        Text {
          visible: root.lastError !== ""
          width: parent.width
          text: "! " + root.lastError
          textFormat: Text.PlainText
          color: root.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          wrapMode: Text.WordWrap
        }

        Text {
          visible: !root.installed
          width: parent.width
          text: "bumblebee not installed — get it from github.com/perplexityai/bumblebee releases."
          textFormat: Text.PlainText
          color: root.fg
          font.family: root.fontFamily
          font.pixelSize: Style.font.body
          wrapMode: Text.WordWrap
        }
      }

      // ---- content ----
      Loader {
        id: tabLoader
        width: parent.width
        height: item ? item.implicitHeight : Style.space(80)
        sourceComponent: root.currentTab === "catalog" ? catalogTab
                       : root.currentTab === "log" ? logTab
                       : exposuresTab
      }
    }
  }

  // ---- Exposures tab ----
  Component {
    id: exposuresTab

    Flickable {
      width: parent.width
      implicitHeight: Math.min(expCol.implicitHeight, Style.space(340))
      height: implicitHeight
      contentWidth: width
      contentHeight: expCol.implicitHeight
      clip: true

      Column {
        id: expCol
        width: parent.width
        spacing: Style.space(6)

        PanelSectionHeader {
          width: parent.width
          text: "KNOWN EXPOSURES"
          foreground: root.fg
          fontFamily: root.fontFamily
        }

        Rectangle {
          visible: root.exposures.length === 0
          width: parent.width
          height: Style.space(44)
          radius: Style.cornerRadius
          color: root.fgFill(0.04)
          border.color: root.fgFill(0.08)

          Text {
            anchors.centerIn: parent
            width: parent.width - Style.space(24)
            text: "No known exposures — " + root.catalogEntries + " " +
                  (root.catalogEntries === 1 ? "advisory" : "advisories") + " watched"
            textFormat: Text.PlainText
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
          }
        }

        Repeater {
          model: root.exposures

          delegate: Rectangle {
            required property var modelData
            property color sevColor: root.sevUrgent(modelData.severity) ? root.urgent : root.accent
            width: expCol.width
            height: expRow.implicitHeight + Style.space(16)
            radius: Style.cornerRadius
            color: root.fgFill(0.04)
            border.color: root.sevUrgent(modelData.severity)
                          ? Qt.rgba(sevColor.r, sevColor.g, sevColor.b, 0.3)
                          : root.fgFill(0.08)

            Row {
              id: expRow
              width: parent.width - Style.space(24)
              anchors.centerIn: parent
              spacing: Style.space(10)

              Column {
                width: parent.width - sevChip.width - parent.spacing
                spacing: Style.space(2)
                anchors.verticalCenter: parent.verticalCenter

                Text {
                  width: parent.width
                  text: modelData.name ? String(modelData.name) : "(unnamed advisory)"
                  textFormat: Text.PlainText
                  color: root.fg
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  elide: Text.ElideRight
                }
                Text {
                  width: parent.width
                  text: root.exposureSub(modelData)
                  textFormat: Text.PlainText
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                }
              }

              // Severity chip: urgent for critical/high, accent otherwise
              Rectangle {
                id: sevChip
                height: Style.space(20)
                width: Math.min(sevText.implicitWidth + Style.space(12), Style.space(110))
                radius: Style.cornerRadius
                color: Qt.rgba(sevColor.r, sevColor.g, sevColor.b, 0.15)
                anchors.verticalCenter: parent.verticalCenter

                Text {
                  id: sevText
                  anchors.centerIn: parent
                  width: parent.width - Style.space(12)
                  text: String(modelData.severity || "?").toUpperCase()
                  textFormat: Text.PlainText
                  color: sevColor
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: true
                  elide: Text.ElideRight
                  horizontalAlignment: Text.AlignHCenter
                }
              }
            }
          }
        }
      }
    }
  }

  // ---- Catalog tab ----
  Component {
    id: catalogTab

    Column {
      width: parent.width
      spacing: Style.space(10)

      PanelSectionHeader {
        width: parent.width
        text: "EXPOSURE CATALOG"
        foreground: root.fg
        fontFamily: root.fontFamily
      }

      Rectangle {
        width: parent.width
        height: catStats.implicitHeight + Style.space(16)
        radius: Style.cornerRadius
        color: root.fgFill(0.04)
        border.color: root.fgFill(0.08)

        Row {
          id: catStats
          width: parent.width - Style.space(24)
          anchors.centerIn: parent
          spacing: Style.space(12)

          Text {
            id: catCount
            anchors.verticalCenter: parent.verticalCenter
            text: String(root.catalogEntries)
            textFormat: Text.PlainText
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.subtitle
            font.bold: true
          }

          Column {
            width: parent.width - catCount.implicitWidth - parent.spacing
            spacing: Style.space(2)
            anchors.verticalCenter: parent.verticalCenter

            Text {
              width: parent.width
              text: root.catalogEntries === 1 ? "advisory watched" : "advisories watched"
              textFormat: Text.PlainText
              color: root.fg
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              elide: Text.ElideRight
            }
            Text {
              width: parent.width
              text: "add advisories in ~/.config/omarchy/plugins-data/bumblebee/catalog.d/"
              textFormat: Text.PlainText
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }
          }
        }
      }

      Repeater {
        model: root.catalogNames

        delegate: Text {
          required property string modelData
          width: parent.width
          text: "· " + String(modelData)
          textFormat: Text.PlainText
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }

  // ---- Log tab ----
  Component {
    id: logTab

    Flickable {
      width: parent.width
      implicitHeight: Math.min(logCol.implicitHeight, Style.space(340))
      height: implicitHeight
      contentWidth: width
      contentHeight: logCol.implicitHeight
      clip: true

      Column {
        id: logCol
        width: parent.width
        spacing: Style.space(6)

        PanelSectionHeader {
          width: parent.width
          text: "SCAN LOG"
          foreground: root.fg
          fontFamily: root.fontFamily
        }

        Rectangle {
          visible: root.scanLog.length === 0
          width: parent.width
          height: Style.space(44)
          radius: Style.cornerRadius
          color: root.fgFill(0.04)
          border.color: root.fgFill(0.08)

          Text {
            anchors.centerIn: parent
            text: "No scans yet"
            textFormat: Text.PlainText
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }
        }

        Repeater {
          model: root.scanLog

          delegate: Row {
            required property var modelData
            width: logCol.width
            spacing: Style.space(8)

            Rectangle {
              width: Style.space(7)
              height: Style.space(7)
              radius: width / 2
              anchors.verticalCenter: parent.verticalCenter
              color: root.logStatusColor(modelData.status)
            }

            Column {
              width: parent.width - Style.space(7) - logMetaText.implicitWidth - parent.spacing * 2
              spacing: 0

              Text {
                width: parent.width
                text: String(modelData.status || "unknown") + " · " +
                      (typeof modelData.exposure_count === "number" ? modelData.exposure_count : 0) +
                      " exposures"
                textFormat: Text.PlainText
                color: root.fg
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                elide: Text.ElideRight
              }
              Text {
                visible: !!modelData.error
                width: parent.width
                text: String(modelData.error || "")
                textFormat: Text.PlainText
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }

            Text {
              id: logMetaText
              anchors.verticalCenter: parent.verticalCenter
              text: root.logMeta(modelData)
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
