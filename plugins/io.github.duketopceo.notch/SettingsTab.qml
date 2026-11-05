import QtQuick
import qs.Commons as Commons
import "Settings.js" as Settings

// Settings tab: two columns of label + value rows. Clicking a bool toggles
// it, a choice cycles it, and an int has - / + buttons. Changes go through
// notch.setSetting, which persists them in the plugin's shell.json entry.
Item {
  id: tab

  property var notch: null

  readonly property color textColor: notch ? notch.textColor : "white"
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""
  readonly property var settings: notch ? notch.settings : Settings.resolve(null)

  function change(key, dir) {
    if (notch) notch.setSetting(key, Settings.next(settings, key, dir))
  }

  readonly property int gutter: 16
  readonly property int headerH: 28
  readonly property int rowH: Math.max(36, Math.min(56, Math.floor((height - headerH) / Math.ceil(Settings.FIELDS.length / 2))))

  Text {
    id: head
    textFormat: Text.PlainText
    text: "Notch settings"
    color: tab.textColor
    font.family: tab.family
    font.pixelSize: Commons.Style.font.title
    font.weight: Font.DemiBold
    height: tab.headerH
    verticalAlignment: Text.AlignVCenter
  }

  NotchScroll {
    anchors.top: head.bottom
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    rowHeight: tab.rowH
    contentHeight: flow.height
    contentWidth: width

  Flow {
    id: flow
    width: parent.width
    spacing: 0

    Repeater {
      model: Settings.FIELDS

      Item {
        id: row
        required property var modelData
        required property int index
        readonly property int padL: index % 2 === 1 ? tab.gutter / 2 : 0
        readonly property int padR: index % 2 === 0 ? tab.gutter / 2 : 0
        readonly property bool isInt: row.modelData.type === "int"
        width: Math.floor(tab.width / 2)
        height: tab.rowH

        Rectangle { anchors.bottom: parent.bottom; x: row.padL; width: parent.width - row.padL - row.padR; height: 1; color: Qt.rgba(1, 1, 1, 0.07) }

        Text {
          textFormat: Text.PlainText
          anchors.left: parent.left
          anchors.leftMargin: row.padL
          anchors.verticalCenter: parent.verticalCenter
          text: row.modelData.label
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: Commons.Style.font.body
        }

        Row {
          anchors.right: parent.right
          anchors.rightMargin: row.padR
          anchors.verticalCenter: parent.verticalCenter
          spacing: 4

          Rectangle {
            visible: row.isInt
            width: 26; height: 26; radius: 13
            color: minus.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "−"
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: Commons.Style.font.title
            }
            MouseArea { id: minus; anchors.fill: parent; hoverEnabled: true; onClicked: tab.change(row.modelData.key, -1) }
          }

          Rectangle {
            id: pill
            width: row.isInt ? 72 : 56
            height: 26; radius: 13
            readonly property bool on: row.modelData.type === "bool" && tab.settings[row.modelData.key] === true
            color: on ? Qt.rgba(1, 1, 1, 0.28) : (pillHit.containsMouse && !row.isInt ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1))
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: Settings.format(row.modelData, tab.settings[row.modelData.key])
              color: pill.on ? Commons.Color.accent : tab.textColor
              font.family: tab.family
              font.pixelSize: Commons.Style.font.body
            }
            MouseArea {
              id: pillHit
              anchors.fill: parent
              hoverEnabled: true
              enabled: !row.isInt
              cursorShape: row.isInt ? Qt.ArrowCursor : Qt.PointingHandCursor
              onClicked: tab.change(row.modelData.key, 1)
            }
          }

          Rectangle {
            visible: row.isInt
            width: 26; height: 26; radius: 13
            color: plus.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "+"
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: Commons.Style.font.title
            }
            MouseArea { id: plus; anchors.fill: parent; hoverEnabled: true; onClicked: tab.change(row.modelData.key, 1) }
          }
        }
      }
    }
  }
  }
}
