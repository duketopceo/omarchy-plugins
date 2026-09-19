import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "lukedaduke.nexus"
  ipcTarget: "lukedaduke.nexus"

  property var usbDevices: []
  property var btDevices: []
  property var netDevices: []
  property var storageDevices: []
  property bool isRefreshing: false
  property string selectedTab: "overview" // "overview", "usb", "bt", "net", "storage"
  property real animPulse: 0.0

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color urgent: Color.urgent
  readonly property color accent: Color.accent
  readonly property color muted: Color.muted
  readonly property color cardBg: Qt.rgba(fg.r, fg.g, fg.b, 0.04)
  readonly property color cardBorder: Qt.rgba(fg.r, fg.g, fg.b, 0.08)
  readonly property string pluginRoot: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }

  NumberAnimation on animPulse {
    from: 0.3
    to: 1.0
    duration: 1400
    loops: Animation.Infinite
    running: root.opened
    easing.type: Easing.InOutSine
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

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: statusProc
    command: [root.py, root.pluginRoot + "/bin/probe_nexus.py"]
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
          if (data.ok) {
            root.usbDevices = (data.usb || []).slice(0, 64)
            root.btDevices = (data.bluetooth || []).slice(0, 64)
            root.netDevices = (data.network || []).slice(0, 64)
            root.storageDevices = (data.storage || []).slice(0, 64)
          }
        } catch (e) {}
      }
    }
    // Helper tracebacks land here — collect so a probe crash is visible
    // in the journal instead of looking like an empty topology.
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var err = String(text || "").trim()
        if (err)
          console.warn("probe_nexus stderr: " + err.substring(0, 500))
      }
    }
    onExited: {
      statusDeadline.stop()
      root.isRefreshing = false
    }
  }

  // Hard whole-job deadline: a stuck probe is killed and reaped. This sits
  // *above* the helper's own 8s SIGALRM cap (worst-case legitimate run is
  // ~6s: three sequential helper calls at 2s each), so slow-but-healthy
  // probes always finish before the watchdog fires — it is purely a
  // stuck-process backstop. probe_nexus.py calls os.setsid() and keeps
  // helpers in its own session group, so a group-kill reaches the whole
  // tree even if Python is stuck inside a helper wait.
  Timer {
    id: statusDeadline
    interval: 9000
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
    interval: 3000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󱐋"
    tooltipText: "Nexus · Interconnect Map"
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
    contentWidth: panel.fittedContentWidth(Style.space(460), 500)
    contentHeight: panel.fittedContentHeight(mainColumn.implicitHeight, 720)

    Column {
      id: mainColumn
      width: parent.width
      spacing: Style.space(12)

      // Top Header Card
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
              anchors.centerIn: parent
              text: "󱐋"
              color: root.accent
              font.pixelSize: 20
            }
          }

          Column {
            Layout.fillWidth: true
            spacing: 2
            Text {
              text: "SYSTEM TOPOLOGY MAP"
              color: root.fg
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.body
              font.bold: true
            }
            Text {
              text: "All physical, wireless, and network interconnects"
              color: root.muted
              font.pixelSize: 10
            }
          }

          // Active Pulse Pill
          Rectangle {
            height: 22
            width: 70
            radius: 11
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.2)
            RowLayout {
              anchors.centerIn: parent
              spacing: 6
              Rectangle {
                width: 6
                height: 6
                radius: 3
                color: root.accent
                opacity: root.animPulse
              }
              Text {
                text: "ONLINE"
                color: root.accent
                font.pixelSize: 9
                font.bold: true
              }
            }
          }
        }
      }

      // Segmented Pill Navigation
      RowLayout {
        width: parent.width
        spacing: 6

        Repeater {
          model: [
            { id: "overview", label: "OVERVIEW" },
            { id: "usb", label: "USB (" + root.usbDevices.length + ")" },
            { id: "bt", label: "BLUETOOTH (" + root.btDevices.length + ")" },
            { id: "net", label: "NETWORK (" + root.netDevices.length + ")" },
            { id: "storage", label: "STORAGE (" + root.storageDevices.length + ")" }
          ]

          delegate: Rectangle {
            height: 26
            Layout.fillWidth: true
            radius: 6
            color: root.selectedTab === modelData.id ? root.accent : root.cardBg
            border.color: root.selectedTab === modelData.id ? root.accent : root.cardBorder
            border.width: 1

            Text {
              anchors.centerIn: parent
              text: modelData.label
              textFormat: Text.PlainText
              color: root.selectedTab === modelData.id ? Color.background : root.fg
              font.pixelSize: 10
              font.bold: true
            }

            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.selectedTab = modelData.id
            }
          }
        }
      }

      // Scrollable Node Graph Area
      Flickable {
        width: parent.width
        height: Math.min(500, contentColumn.implicitHeight)
        contentWidth: width
        contentHeight: contentColumn.implicitHeight
        clip: true

        Column {
          id: contentColumn
          width: parent.width
          spacing: Style.space(10)

          // SECTION 1: INTERNET & MESH
          Column {
            width: parent.width
            spacing: 6
            visible: root.selectedTab === "overview" || root.selectedTab === "net"

            Text {
              text: "NETWORK & ENCRYPTED TUNNELS"
              color: root.muted
              font.pixelSize: 10
              font.bold: true
            }

            Repeater {
              model: root.netDevices
              delegate: Rectangle {
                width: parent.width
                height: 48
                radius: 8
                color: root.cardBg
                border.color: modelData.status === "CONNECTED" ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.3) : root.cardBorder
                border.width: 1

                RowLayout {
                  anchors.fill: parent
                  anchors.leftMargin: 12
                  anchors.rightMargin: 12
                  spacing: 12

                  Text {
                    text: modelData.icon
                    textFormat: Text.PlainText
                    color: modelData.status === "CONNECTED" ? root.accent : root.muted
                    font.pixelSize: 20
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      textFormat: Text.PlainText
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }
                    Text {
                      text: modelData.desc + " · " + modelData.ip
                      textFormat: Text.PlainText
                      color: root.muted
                      font.pixelSize: 10
                    }
                  }

                  Rectangle {
                    width: 74
                    height: 20
                    radius: 4
                    color: modelData.status === "CONNECTED" ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.15) : Qt.rgba(root.muted.r, root.muted.g, root.muted.b, 0.15)
                    Text {
                      anchors.centerIn: parent
                      text: modelData.status
                      textFormat: Text.PlainText
                      color: modelData.status === "CONNECTED" ? root.accent : root.muted
                      font.pixelSize: 9
                      font.bold: true
                    }
                  }
                }
              }
            }
          }

          // SECTION 2: BLUETOOTH RADIOS
          Column {
            width: parent.width
            spacing: 6
            visible: root.selectedTab === "overview" || root.selectedTab === "bt"

            Text {
              text: "PAIRED WIRELESS PERIPHERALS"
              color: root.muted
              font.pixelSize: 10
              font.bold: true
            }

            Repeater {
              model: root.btDevices
              delegate: Rectangle {
                width: parent.width
                height: 48
                radius: 8
                color: root.cardBg
                border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.3)
                border.width: 1

                RowLayout {
                  anchors.fill: parent
                  anchors.leftMargin: 12
                  anchors.rightMargin: 12
                  spacing: 12

                  Text {
                    text: modelData.icon
                    textFormat: Text.PlainText
                    color: root.accent
                    font.pixelSize: 20
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      textFormat: Text.PlainText
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }
                    Text {
                      text: modelData.category + " · " + modelData.desc
                      textFormat: Text.PlainText
                      color: root.muted
                      font.pixelSize: 10
                    }
                  }

                  Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: root.accent
                    opacity: root.animPulse
                  }
                }
              }
            }
          }

          // SECTION 3: USB BUS CASCADE
          Column {
            width: parent.width
            spacing: 6
            visible: root.selectedTab === "overview" || root.selectedTab === "usb"

            Text {
              text: "USB TREE & DOCK INTERCONNECTS"
              color: root.muted
              font.pixelSize: 10
              font.bold: true
            }

            Repeater {
              model: root.usbDevices
              delegate: Rectangle {
                width: parent.width
                height: 48
                radius: 8
                color: modelData.is_hub ? Qt.rgba(root.muted.r, root.muted.g, root.muted.b, 0.05) : root.cardBg
                border.color: modelData.status === "ONLINE" ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.2) : root.cardBorder
                border.width: 1

                RowLayout {
                  anchors.fill: parent
                  anchors.leftMargin: 10 + (modelData.tier * 10)
                  anchors.rightMargin: 12
                  spacing: 10

                  Text {
                    text: modelData.tier > 0 ? "└─" : "•"
                    textFormat: Text.PlainText
                    color: root.muted
                    font.pixelSize: 11
                  }

                  Text {
                    text: modelData.icon
                    textFormat: Text.PlainText
                    color: modelData.status === "ONLINE" ? (modelData.is_hub ? root.muted : root.accent) : root.muted
                    font.pixelSize: 18
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      textFormat: Text.PlainText
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: !modelData.is_hub
                      elide: Text.ElideRight
                    }
                    Text {
                      text: modelData.desc + " · " + modelData.speed
                      textFormat: Text.PlainText
                      color: root.muted
                      font.pixelSize: 10
                    }
                  }

                  Rectangle {
                    width: 64
                    height: 18
                    radius: 4
                    color: modelData.status === "ONLINE" ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12) : Qt.rgba(root.muted.r, root.muted.g, root.muted.b, 0.12)
                    Text {
                      anchors.centerIn: parent
                      text: modelData.status
                      textFormat: Text.PlainText
                      color: modelData.status === "ONLINE" ? root.accent : root.muted
                      font.pixelSize: 8
                      font.bold: true
                    }
                  }
                }
              }
            }
          }

          // SECTION 4: STORAGE SILICON
          Column {
            width: parent.width
            spacing: 6
            visible: root.selectedTab === "overview" || root.selectedTab === "storage"

            Text {
              text: "STORAGE SILICON & VOLUMES"
              color: root.muted
              font.pixelSize: 10
              font.bold: true
            }

            Repeater {
              model: root.storageDevices
              delegate: Rectangle {
                width: parent.width
                height: 48
                radius: 8
                color: root.cardBg
                border.color: root.cardBorder
                border.width: 1

                RowLayout {
                  anchors.fill: parent
                  anchors.leftMargin: 12
                  anchors.rightMargin: 12
                  spacing: 12

                  Text {
                    text: modelData.icon
                    textFormat: Text.PlainText
                    color: root.accent
                    font.pixelSize: 20
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      textFormat: Text.PlainText
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }
                    Text {
                      text: modelData.desc + " · " + modelData.mount
                      textFormat: Text.PlainText
                      color: root.muted
                      font.pixelSize: 10
                    }
                  }

                  Rectangle {
                    width: 68
                    height: 20
                    radius: 4
                    color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.15)
                    Text {
                      anchors.centerIn: parent
                      text: modelData.status
                      textFormat: Text.PlainText
                      color: root.accent
                      font.pixelSize: 9
                      font.bold: true
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
}
