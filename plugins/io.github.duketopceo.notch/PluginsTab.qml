import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
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
  readonly property int gap: 8
  readonly property int cols: ids.length > 9 ? 4 : 3
  readonly property int rows: Math.max(1, Math.ceil(ids.length / cols))
  // Tiles share the whole height when they fit (up to 120 px); more rows scroll.
  readonly property int tileH: Math.max(64, Math.min(120, Math.floor((height - (rows - 1) * gap) / rows)))

  Text {
    textFormat: Text.PlainText
    anchors.centerIn: parent
    visible: tab.ids.length === 0
    text: "No tray plugins on the bar"
    color: tab.dimColor
    font.family: tab.family
    font.pixelSize: Commons.Style.font.bodySmall
  }

  NotchScroll {
    anchors.fill: parent
    rowHeight: tab.tileH + tab.gap
    contentHeight: flow.height
    contentWidth: width

  Flow {
    id: flow
    width: parent.width
    spacing: tab.gap

    Repeater {
      model: tab.ids

      Rectangle {
        id: slot
        required property string modelData
        property var info: Plugins.slotInfo(slot.modelData, "", tab.home)
        width: Math.floor((tab.width - (tab.cols - 1) * tab.gap) / tab.cols)
        height: tab.tileH
        radius: 12
        color: hit.containsMouse ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)

        // Only hand an icon file to Image once it is known to exist (no warnings).
        property bool imageOk: false
        FileView {
          path: slot.info.image
          printErrors: false
          onLoaded: slot.imageOk = true
          onLoadFailed: slot.imageOk = false
        }
        FileView {
          path: Plugins.manifestPath(tab.home, slot.modelData)
          blockLoading: true
          printErrors: false
          onLoaded: slot.info = Plugins.slotInfo(slot.modelData, text(), tab.home)
          onLoadFailed: slot.info = Plugins.slotInfo(slot.modelData, "", tab.home)
        }

        Column {
          anchors.centerIn: parent
          width: parent.width - 16
          spacing: 8

          Item {
            width: parent.width; height: 32
            Image {
              id: iconImg
              anchors.centerIn: parent
              width: 28; height: 28
              visible: slot.imageOk && status === Image.Ready
              source: slot.imageOk ? "file://" + slot.info.image : ""
              sourceSize: Qt.size(56, 56)
              fillMode: Image.PreserveAspectFit
              asynchronous: true
            }
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              visible: !slot.imageOk || iconImg.status !== Image.Ready
              text: slot.info.glyph
              color: tab.textColor
              font.family: tab.family
              font.pixelSize: Commons.Style.font.display
            }
          }
          Text {
            textFormat: Text.PlainText
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: tab.notch && tab.notch.openFailed === slot.modelData ? "not on the bar" : slot.info.name
            color: tab.textColor
            font.family: tab.family
            font.pixelSize: Commons.Style.font.body
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
}
