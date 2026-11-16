import QtQuick 6.11
import qs.Commons as Commons

// System: battery, power profile, fan mode, CPU, memory, network and
// Tailscale (Status.js rows). The root samples them only while a System page
// is open. The fan row opens the Resource & Fan panel when that plugin is
// installed.
Item {
  id: page

  property var island: null
  property int maxRows: 0

  readonly property int rowH: Commons.Style.spacing.controlHeight
  readonly property int gap: Commons.Style.spacing.sm
  readonly property var rows: page.island ? page.island.systemRows : []
  readonly property int labelW: Commons.Style.space(120)

  function count() { return Math.max(1, page.rows.length) }
  function heightFor(n) { return Math.max(1, n) * (page.rowH + page.gap) }

  EmptyNote {
    visible: page.rows.length === 0
    width: parent.width
    height: page.rowH + page.gap
    text: "Reading system state"
  }

  Column {
    width: parent.width
    spacing: page.gap

    Repeater {
      model: page.rows.slice(0, Math.max(0, page.maxRows))

      Item {
        id: item
        required property var modelData
        width: parent.width
        height: page.rowH

        Txt {
          id: label
          width: page.labelW
          anchors.verticalCenter: parent.verticalCenter
          opacity: 0.65
          text: item.modelData.label
        }

        Txt {
          id: value
          anchors.left: label.right
          anchors.verticalCenter: parent.verticalCenter
          width: Math.min(implicitWidth, parent.width - page.labelW - meter.width - openFan.width - Commons.Style.spacing.huge)
          font.features: { "tnum": 1 }
          text: item.modelData.value
        }

        // A thin meter for rows with a level (battery, CPU, memory).
        Rectangle {
          id: meter
          visible: typeof item.modelData.level === "number"
          width: visible ? Commons.Style.space(140) : 0
          height: 4
          radius: 2
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          color: Commons.Color.menu.selectedBackground
          Rectangle {
            width: parent.width * Math.max(0, Math.min(1, item.modelData.level || 0))
            height: parent.height
            radius: parent.radius
            color: (item.modelData.level || 0) >= 0.9 && item.modelData.id !== "battery" ? Commons.Color.urgent : Commons.Color.accent
          }
        }

        ActivityButton {
          id: openFan
          visible: item.modelData.id === "fan" && page.island !== null && page.island.fanPanel
          width: visible ? implicitWidth : 0
          label: "Open"
          hint: "Open the fan panel"
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          onClicked: page.island.openFanPanel()
        }
      }
    }
  }
}
