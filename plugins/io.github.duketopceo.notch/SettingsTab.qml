import QtQuick
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

  Flow {
    anchors.fill: parent
    spacing: 0

    Repeater {
      model: Settings.FIELDS

      Item {
        id: row
        required property var modelData
        readonly property bool isInt: row.modelData.type === "int"
        width: Math.floor(tab.width / 2)
        height: 32

        Text {
          textFormat: Text.PlainText
          anchors.left: parent.left
          anchors.leftMargin: 4
          anchors.verticalCenter: parent.verticalCenter
          text: row.modelData.label
          color: tab.dimColor
          font.family: tab.family
          font.pixelSize: 10
        }

        Row {
          anchors.right: parent.right
          anchors.rightMargin: 12
          anchors.verticalCenter: parent.verticalCenter
          spacing: 4

          Rectangle {
            visible: row.isInt
            width: 18; height: 18; radius: 9
            color: minus.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "−"
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 12
            }
            MouseArea { id: minus; anchors.fill: parent; hoverEnabled: true; onClicked: tab.change(row.modelData.key, -1) }
          }

          Rectangle {
            id: pill
            width: row.isInt ? 54 : 48
            height: 20; radius: 10
            readonly property bool on: row.modelData.type === "bool" && tab.settings[row.modelData.key] === true
            color: on ? Qt.rgba(0.5, 0.75, 0.5, 0.35) : (pillHit.containsMouse && !row.isInt ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1))
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: Settings.format(row.modelData, tab.settings[row.modelData.key])
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 10
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
            width: 18; height: 18; radius: 9
            color: plus.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.1)
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "+"
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 12
            }
            MouseArea { id: plus; anchors.fill: parent; hoverEnabled: true; onClicked: tab.change(row.modelData.key, 1) }
          }
        }
      }
    }
  }
}
