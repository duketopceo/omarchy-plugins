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

  property string currentTab: Tabs.DEFAULT_TAB   // owned by the window (it sizes the panel); bound by the Loader
  signal tabSelected(string id)
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
    anchors.leftMargin: panel.tab && panel.tab.id === "home" ? 24 : 16
    anchors.rightMargin: anchors.leftMargin
    anchors.bottomMargin: panel.tab && panel.tab.id === "home" ? 20 : 12
    opacity: Math.max(0, (panel.progress - 0.5) * 2)

    // ---------------------------------------------------------- tab strip
    // Equal-width chips with glyph + short label when they all fit; otherwise
    // the selected chip shows its label and the rest share what is left as
    // glyph-only chips. Widths come from measured text, so nothing truncates.
    Row {
      id: strip
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.right: parent.right
      height: 26
      spacing: 4

      readonly property int count: Math.max(1, panel.tabs.length)
      readonly property int glyphW: 12
      readonly property int padX: 10
      readonly property int equalW: Math.floor((width - (count - 1) * spacing) / count)
      readonly property bool labelsFit: equalW >= glyphW + 4 + longest.advanceWidth + padX
      readonly property int selW: glyphW + 4 + current.advanceWidth + padX
      readonly property int otherW: count > 1 ? Math.max(glyphW + 10, Math.floor((width - selW - (count - 1) * spacing) / (count - 1))) : width

      TextMetrics {
        id: longest
        font.family: panel.family
        font.pixelSize: Commons.Style.font.caption
        text: {
          var best = ""
          for (var i = 0; i < panel.tabs.length; i++) {
            var t = panel.tabs[i].short || panel.tabs[i].title
            if (t.length > best.length) best = t
          }
          return best
        }
      }
      TextMetrics {
        id: current
        font.family: panel.family
        font.pixelSize: Commons.Style.font.caption
        text: panel.tab ? (panel.tab.short || panel.tab.title) : ""
      }

      Repeater {
        model: panel.tabs
        Rectangle {
          id: chip
          required property var modelData
          readonly property bool selected: chip.modelData.id === panel.tab.id
          readonly property bool showLabel: strip.labelsFit || selected
          width: strip.labelsFit ? strip.equalW : (selected ? strip.selW : strip.otherW)
          height: strip.height
          radius: height / 2
          color: selected ? Qt.rgba(1, 1, 1, 0.16) : (hit.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent")
          Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
          Row {
            anchors.centerIn: parent
            spacing: 4
            Text {
              textFormat: Text.PlainText
              text: chip.modelData.glyph
              color: chip.selected ? panel.textColor : panel.dimColor
              font.family: panel.family
              font.pixelSize: Commons.Style.font.bodySmall
              anchors.verticalCenter: parent.verticalCenter
            }
            Text {
              visible: chip.showLabel
              textFormat: Text.PlainText
              text: chip.modelData.short || chip.modelData.title
              color: chip.selected ? panel.textColor : panel.dimColor
              font.family: panel.family
              font.pixelSize: Commons.Style.font.caption
              anchors.verticalCenter: parent.verticalCenter
            }
          }
          MouseArea {
            id: hit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: panel.tabSelected(chip.modelData.id)
          }
        }
      }
    }

    // ---------------------------------------------------------- content
    Item {
      id: content
      anchors.top: strip.bottom
      anchors.topMargin: panel.tab && panel.tab.id === "home" ? 14 : 8
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      clip: true

      Loader {
        id: loader
        anchors.fill: parent
        source: panel.resolved.source
        onLoaded: { if (item) item.notch = panel.notch; swapFade.restart() }
        NumberAnimation { id: swapFade; target: loader; property: "opacity"; from: 0; to: 1; duration: 220; easing.type: Easing.OutQuad }
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
        font.pixelSize: Commons.Style.font.bodySmall
      }
    }
  }
}
