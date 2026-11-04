import QtQuick
import Quickshell
import Quickshell.Io
import "Plugins.js" as Plugins

// Plugins tab: one slot per plugin in the bar's tray section. Name and icon
// come from the plugin's manifest; clicking opens its panel through the shell.
Item {
  id: tab

  property var notch: null

  readonly property color textColor: notch ? notch.textColor : "white"
  readonly property color dimColor: notch ? notch.dimColor : "gray"
  readonly property string family: notch ? notch.fontFamily : ""
  readonly property string home: Quickshell.env("HOME")
  readonly property var ids: Plugins.trayIds(notch ? notch.shellConfig : null)

  Text {
    textFormat: Text.PlainText
    anchors.centerIn: parent
    visible: tab.ids.length === 0
    text: "No tray plugins on the bar"
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: 11
  }

  Flow {
    anchors.fill: parent
    spacing: 6

    Repeater {
      model: tab.ids

      Rectangle {
        id: slot
        required property string modelData
        property var info: Plugins.slotInfo(slot.modelData, "", tab.home)
        width: Math.floor((tab.width - 3 * 6) / 4)
        height: 36
        radius: 8
        color: hit.containsMouse ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)

        FileView {
          path: Plugins.manifestPath(tab.home, slot.modelData)
          blockLoading: true
          printErrors: false
          onLoaded: slot.info = Plugins.slotInfo(slot.modelData, text(), tab.home)
          onLoadFailed: slot.info = Plugins.slotInfo(slot.modelData, "", tab.home)
        }

        Row {
          anchors.fill: parent
          anchors.leftMargin: 8
          anchors.rightMargin: 6
          spacing: 6

          Item {
            width: 18; height: parent.height
            Image {
              anchors.centerIn: parent
              width: 16; height: 16
              visible: slot.info.image !== "" && status === Image.Ready
              source: slot.info.image !== "" ? "file://" + slot.info.image : ""
              sourceSize: Qt.size(32, 32)
              fillMode: Image.PreserveAspectFit
              asynchronous: true
            }
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              visible: slot.info.image === ""
              text: slot.info.glyph
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: 14
            }
          }
          Text {
            textFormat: Text.PlainText
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 24
            elide: Text.ElideRight
            text: slot.info.name
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: 10
          }
        }

        MouseArea {
          id: hit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: if (tab.notch) tab.notch.openPlugin(slot.modelData)
        }
      }
    }
  }
}
