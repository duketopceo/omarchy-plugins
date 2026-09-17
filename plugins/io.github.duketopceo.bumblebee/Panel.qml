import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "io.github.duketopceo.bumblebee"
  ipcTarget: "io.github.duketopceo.bumblebee"

  property bool installed: false
  property int ageS: -1
  property int exposureCount: 0
  property var exposures: []
  property int catalogEntries: 0
  property bool partial: false
  property string lastError: ""
  property bool isRefreshing: false

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property color muted: Color.muted
  readonly property color cardBg: Qt.rgba(fg.r, fg.g, fg.b, 0.04)
  readonly property color cardBorder: Qt.rgba(fg.r, fg.g, fg.b, 0.08)
  // State color: muted until installed, urgent on any exposure, accent when clean.
  readonly property color stateColor: !installed ? muted : (exposureCount > 0 ? urgent : accent)
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
    if (!statusProc.running) {
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
    contentWidth: panel.fittedContentWidth(Style.space(440), 480)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 640)

    Column {
      id: mainColumn
      width: parent.width
      spacing: Style.space(12)

      // Header card
      Rectangle {
        width: parent.width
        height: 64
        radius: 10
        color: Qt.rgba(root.stateColor.r, root.stateColor.g, root.stateColor.b, 0.08)
        border.color: Qt.rgba(root.stateColor.r, root.stateColor.g, root.stateColor.b, 0.25)
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
            color: Qt.rgba(root.stateColor.r, root.stateColor.g, root.stateColor.b, 0.2)
            Text {
              anchors.centerIn: parent
              text: "󰒃"
              textFormat: Text.PlainText
              color: root.stateColor
              font.pixelSize: 20
            }
          }

          Column {
            Layout.fillWidth: true
            spacing: 2
            Text {
              width: parent.width
              text: "SUPPLY CHAIN EXPOSURES"
              textFormat: Text.PlainText
              color: root.fg
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
              elide: Text.ElideRight
            }
            Text {
              width: parent.width
              text: root.lastError !== ""
                    ? "scan failed · " + root.lastError
                    : (root.ageS >= 0 ? "scanned " + root.fmtAge(root.ageS) + " ago"
                                      : "awaiting first scan")
              textFormat: Text.PlainText
              color: root.muted
              font.pixelSize: 10
              elide: Text.ElideRight
            }
          }

          Column {
            spacing: 4
            Layout.alignment: Qt.AlignVCenter

            // Count pill
            Rectangle {
              height: 22
              width: pillText.implicitWidth + 16
              radius: 11
              color: Qt.rgba(root.stateColor.r, root.stateColor.g, root.stateColor.b, 0.2)
              Text {
                id: pillText
                anchors.centerIn: parent
                text: !root.installed ? "SETUP"
                      : (root.exposureCount > 99 ? "99+" : String(root.exposureCount))
                textFormat: Text.PlainText
                color: root.stateColor
                font.pixelSize: 9
                font.bold: true
              }
            }

            // Partial-scan warning chip
            Rectangle {
              height: 16
              width: partialText.implicitWidth + 12
              radius: 8
              visible: root.installed && root.partial
              color: Qt.rgba(root.urgent.r, root.urgent.g, root.urgent.b, 0.15)
              border.color: Qt.rgba(root.urgent.r, root.urgent.g, root.urgent.b, 0.4)
              border.width: 1
              Text {
                id: partialText
                anchors.centerIn: parent
                text: "PARTIAL SCAN"
                textFormat: Text.PlainText
                color: root.urgent
                font.pixelSize: 8
                font.bold: true
              }
            }
          }
        }
      }

      // Bordered setup pane when the scanner binary is missing
      Rectangle {
        visible: !root.installed
        width: parent.width
        height: setupColumn.implicitHeight + 24
        radius: 8
        color: root.cardBg
        border.color: root.cardBorder
        border.width: 1

        Column {
          id: setupColumn
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          anchors.margins: 12
          spacing: 6

          Text {
            text: "BUMBLEBEE NOT INSTALLED"
            textFormat: Text.PlainText
            color: root.fg
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }
          Text {
            width: parent.width
            text: "Install bumblebee from github.com/perplexityai/bumblebee releases. It inventories lockfiles and exact-matches them against the advisory catalog."
            textFormat: Text.PlainText
            color: root.muted
            font.pixelSize: 10
            wrapMode: Text.WordWrap
          }
        }
      }

      // Exposure list (invisible while uninstalled — positioners skip it)
      Flickable {
        visible: root.installed
        width: parent.width
        height: Math.min(340, listColumn.implicitHeight)
        contentWidth: width
        contentHeight: listColumn.implicitHeight
        clip: true

        Column {
          id: listColumn
          width: parent.width
          spacing: 6

          // Empty state
          Rectangle {
            visible: root.exposures.length === 0
            width: parent.width
            height: 56
            radius: 8
            color: root.cardBg
            border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.25)
            border.width: 1

            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: 12
              anchors.rightMargin: 12
              spacing: 12

              Text {
                text: "󰒃"
                textFormat: Text.PlainText
                color: root.accent
                font.pixelSize: 20
              }

              Column {
                Layout.fillWidth: true
                spacing: 2
                Text {
                  text: "No known exposures"
                  textFormat: Text.PlainText
                  color: root.fg
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }
                Text {
                  text: "watching " + root.catalogEntries + " " +
                        (root.catalogEntries === 1 ? "advisory" : "advisories")
                  textFormat: Text.PlainText
                  color: root.muted
                  font.pixelSize: 10
                }
              }
            }
          }

          Repeater {
            model: root.exposures
            delegate: Rectangle {
              property color sevColor: root.sevUrgent(modelData.severity) ? root.urgent : root.accent
              width: parent.width
              height: 48
              radius: 8
              color: root.cardBg
              border.color: root.sevUrgent(modelData.severity)
                            ? Qt.rgba(sevColor.r, sevColor.g, sevColor.b, 0.3)
                            : root.cardBorder
              border.width: 1

              RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 12

                Column {
                  Layout.fillWidth: true
                  spacing: 2
                  Text {
                    width: parent.width
                    text: modelData.name ? String(modelData.name) : "(unnamed advisory)"
                    textFormat: Text.PlainText
                    color: root.fg
                    font.pixelSize: Style.font.bodySmall
                    font.bold: true
                    elide: Text.ElideRight
                  }
                  Text {
                    width: parent.width
                    text: root.exposureSub(modelData)
                    textFormat: Text.PlainText
                    color: root.muted
                    font.pixelSize: 10
                    elide: Text.ElideRight
                  }
                }

                // Severity chip: urgent for critical/high, accent otherwise
                Rectangle {
                  height: 20
                  width: Math.min(sevText.implicitWidth + 12, 110)
                  radius: 4
                  color: Qt.rgba(sevColor.r, sevColor.g, sevColor.b, 0.15)
                  Text {
                    id: sevText
                    anchors.centerIn: parent
                    width: parent.width - 12
                    text: String(modelData.severity || "?").toUpperCase()
                    textFormat: Text.PlainText
                    color: sevColor
                    font.pixelSize: 9
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

      // Footer hint
      Text {
        width: parent.width
        text: "Add advisories: ~/.config/omarchy/plugins-data/bumblebee/catalog.d/"
        textFormat: Text.PlainText
        color: root.muted
        font.pixelSize: 9
        elide: Text.ElideRight
      }
    }
  }
}
