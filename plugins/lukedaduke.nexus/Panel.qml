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

  function refresh() {
    if (!statusProc.running) {
      isRefreshing = true
      statusProc.running = true
    }
  }

  visible: true
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Process {
    id: statusProc
    command: ["python3", root.pluginRoot + "/bin/probe_nexus.py"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.isRefreshing = false
        try {
          if (!text || text.trim().length === 0) return
          var data = JSON.parse(text)
          if (data.ok) {
            root.usbDevices = data.usb || []
            root.btDevices = data.bluetooth || []
            root.netDevices = data.network || []
            root.storageDevices = data.storage || []
          }
        } catch (e) {}
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

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󱐋 NEXUS"
    fontSize: Style.font.bodySmall
    tooltipText: "System Interconnect Map"
    horizontalMargin: 8.5
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
                    color: modelData.status === "CONNECTED" ? root.accent : root.muted
                    font.pixelSize: 20
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }
                    Text {
                      text: modelData.desc + " · " + modelData.ip
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
                    color: root.accent
                    font.pixelSize: 20
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }
                    Text {
                      text: modelData.category + " · " + modelData.desc
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
                    color: root.muted
                    font.pixelSize: 11
                  }

                  Text {
                    text: modelData.icon
                    color: modelData.status === "ONLINE" ? (modelData.is_hub ? root.muted : root.accent) : root.muted
                    font.pixelSize: 18
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: !modelData.is_hub
                      elide: Text.ElideRight
                    }
                    Text {
                      text: modelData.desc + " · " + modelData.speed
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
                    color: root.accent
                    font.pixelSize: 20
                  }

                  Column {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                      text: modelData.name
                      color: root.fg
                      font.pixelSize: Style.font.bodySmall
                      font.bold: true
                    }
                    Text {
                      text: modelData.desc + " · " + modelData.mount
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
