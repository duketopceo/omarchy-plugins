import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Tabs.js" as Tabs

// The island's hover-expanded content. Fills the island; the top
// `headerHeight` px (the camera / idle row) stay clear. Below it sit a tab
// strip and a content area. Each tab is a QML file named in Tabs.js, loaded
// with a Loader; the loaded item gets `notch` set to the root Notch.qml item.
// A tab whose file does not exist yet shows a quiet "coming soon" line.
// Opaque cover fades in with `progress` so the idle row gives way to it.
Item {
  id: panel

  property bool active: false          // island is open
  property real progress: 0            // 0 collapsed .. 1 expanded
  property int headerHeight: 32
  property var notch: null             // root Notch.qml item, handed to every tab
  property var weather: null           // Model.parseWeather output
  property color islandColor: "black"
  property color textColor: Commons.Color.foreground
  property color dimColor: Commons.Color.muted
  property string family: Commons.Style.font.family
  property date now: new Date()

  property string currentTab: Tabs.DEFAULT_TAB
  readonly property var tabs: Tabs.visibleTabs(notch ? notch.settings : null)
  readonly property var tab: Tabs.select(currentTab, tabs)
  readonly property string pluginDir: notch ? notch.pluginDir : ""

  // tab id -> true/false once its source file has been probed.
  property var sourceExists: ({})
  readonly property var resolved: Tabs.resolve(tab, sourceExists)

  Rectangle {
    anchors.fill: parent
    color: panel.islandColor
    opacity: Math.min(1, panel.progress * 1.6)
    bottomLeftRadius: 24
    bottomRightRadius: 24
  }

  // One probe per tab: does its QML file exist yet?
  Repeater {
    model: Tabs.TABS
    Item {
      id: probe
      required property var modelData
      FileView {
        path: panel.pluginDir !== "" ? panel.pluginDir + "/" + probe.modelData.source : ""
        blockLoading: true
        printErrors: false
        onLoaded: panel.mark(probe.modelData.id, true)
        onLoadFailed: panel.mark(probe.modelData.id, false)
      }
    }
  }
  function mark(id, ok) {
    if (sourceExists[id] === ok) return
    var copy = {}
    for (var k in sourceExists) copy[k] = sourceExists[k]
    copy[id] = ok
    sourceExists = copy
  }

  Item {
    id: body
    anchors.fill: parent
    anchors.topMargin: panel.headerHeight
    anchors.leftMargin: 16
    anchors.rightMargin: 16
    anchors.bottomMargin: 12
    opacity: Math.max(0, (panel.progress - 0.5) * 2)

    // ---------------------------------------------------------- tab strip
    Row {
      id: strip
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.right: parent.right
      height: 24
      spacing: 4

      Repeater {
        model: panel.tabs
        Rectangle {
          id: chip
          required property var modelData
          readonly property bool selected: chip.modelData.id === panel.tab.id
          // The selected chip shows glyph + title; the others only their glyph.
          width: selected ? 84 : Math.floor((strip.width - 84 - (panel.tabs.length - 1) * strip.spacing) / Math.max(1, panel.tabs.length - 1))
          height: strip.height
          radius: 12
          color: selected ? Qt.rgba(1, 1, 1, 0.16) : (hit.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent")
          Row {
            anchors.centerIn: parent
            spacing: 4
            Text {
              textFormat: Text.PlainText
              text: chip.modelData.glyph
              color: chip.selected ? panel.textColor : panel.dimColor
              font.family: panel.family
              font.pixelSize: 12
              anchors.verticalCenter: parent.verticalCenter
            }
            Text {
              visible: chip.selected
              textFormat: Text.PlainText
              text: chip.modelData.title
              color: chip.selected ? panel.textColor : panel.dimColor
              font.family: panel.family
              font.pixelSize: 10
              anchors.verticalCenter: parent.verticalCenter
            }
          }
          MouseArea {
            id: hit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: panel.currentTab = chip.modelData.id
          }
        }
      }
    }

    // ---------------------------------------------------------- content
    Item {
      id: content
      anchors.top: strip.bottom
      anchors.topMargin: 8
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      clip: true

      Loader {
        id: loader
        anchors.fill: parent
        source: panel.resolved.source
        onLoaded: if (item) item.notch = panel.notch
        // Re-hand the notch if the root item is replaced.
        Connections {
          target: panel
          function onNotchChanged() { if (loader.item) loader.item.notch = panel.notch }
        }
      }

      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        visible: panel.resolved.state === "missing" || loader.status === Loader.Error
        text: panel.resolved.state === "missing" ? panel.resolved.message : Tabs.failed(panel.tab).message
        color: panel.dimColor
        font.family: panel.family
        font.pixelSize: 11
      }
    }
  }
}
