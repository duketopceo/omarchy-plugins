import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Tabs.js" as Tabs
import "Motion.js" as Motion
import "Theme.js" as Theme

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
  property color islandColor: notch ? notch.islandColor : "black"
  property color textColor: notch ? notch.textColor : Commons.Color.foreground
  property color dimColor: notch ? notch.dimColor : Commons.Color.muted
  property string family: notch ? notch.fontFamily : Commons.Style.font.family
  readonly property var themeObj: notch && notch.themeObj ? notch.themeObj : Theme.resolve("swift")
  property date now: new Date()

  property string currentTab: Tabs.DEFAULT_TAB   // owned by the window (it sizes the panel); bound by the Loader
  signal tabSelected(string id)
  readonly property var tabs: Tabs.visibleTabs(notch ? notch.settings : null)
  readonly property var tab: Tabs.select(currentTab, tabs)
  readonly property string pluginDir: notch ? notch.pluginDir : ""

  // tab id -> true/false once its source file has been probed.
  property var sourceExists: ({})
  readonly property bool reduce: notch ? notch.reduceMotion : Commons.Style.reduceMotion
  readonly property var resolved: Tabs.resolve(tab, sourceExists)

  Rectangle {
    anchors.fill: parent
    color: panel.islandColor
    opacity: Math.min(1, panel.progress * 1.6)
    bottomLeftRadius: panel.themeObj.islandRadius
    bottomRightRadius: panel.themeObj.islandRadius
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
    anchors.rightMargin: anchors.leftMargin
    anchors.bottomMargin: 14
    // Content waits until the shape is mostly open, fades out first on close.
    readonly property bool shown: panel.active && (panel.reduce || panel.progress > Motion.OPEN_GATE)
    property real fade: shown ? 1 : 0
    Behavior on fade { NumberAnimation { duration: panel.reduce ? Motion.REDUCED_FADE_MS : (body.shown ? Motion.FADE_IN_MS : Motion.FADE_OUT_MS); easing.type: Easing.OutQuad } }
    opacity: fade
    transform: Translate { y: panel.reduce ? 0 : (1 - body.fade) * Motion.CONTENT_SLIDE }

    // ---------------------------------------------------------- tab strip
    // Equal-width chips with glyph + short label when they all fit; otherwise
    // the selected chip shows its label and the rest share what is left as
    // glyph-only chips. Widths come from measured text, so nothing truncates.
    SpringValue { id: indX; target: strip.chipX(strip.selIndex); instant: panel.reduce; duration: Motion.STRIP.duration; bounce: Motion.STRIP.bounce }
    SpringValue { id: indW; target: strip.chipW(strip.selIndex); instant: panel.reduce; duration: Motion.STRIP.duration; bounce: Motion.STRIP.bounce }
    Rectangle {
      x: strip.x + indX.value; y: strip.y; width: indW.value; height: strip.height; radius: height / 2
      color: Qt.rgba(1, 1, 1, 0.16)
    }

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

      // Selected-chip indicator: slides between chips on a spring.
      readonly property int selIndex: { for (var i = 0; i < panel.tabs.length; i++) if (panel.tabs[i].id === panel.tab.id) return i; return 0 }
      function chipX(i) { return labelsFit ? i * (equalW + spacing) : (i < selIndex ? i * (otherW + spacing) : (i === selIndex ? selIndex * (otherW + spacing) : selIndex * (otherW + spacing) + selW + spacing + (i - selIndex - 1) * (otherW + spacing))) }
      function chipW(i) { return labelsFit ? equalW : (i === selIndex ? selW : otherW) }
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
          color: !selected && hit.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
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
      anchors.topMargin: 10
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      clip: true

      // Tab switch: the outgoing tab fades and shifts toward the side it came
      // from, the incoming one slides in from the clicked tab's direction.
      property string shownSource: ""
      property int shownIndex: 0
      property int dir: 1
      readonly property int wantIndex: { for (var i = 0; i < panel.tabs.length; i++) if (panel.tabs[i].id === panel.tab.id) return i; return 0 }
      readonly property string wantSource: panel.resolved.source
      onWantSourceChanged: retarget()
      Component.onCompleted: retarget()
      function retarget() {
        if (wantSource === shownSource) return
        if (shownSource === "" || wantSource === "" || !panel.active) { swapAnim.stop(); applyNow(); return }
        dir = Motion.direction(shownIndex, wantIndex)
        swapAnim.restart()
      }
      function applyNow() { shownSource = wantSource; shownIndex = wantIndex; loader.opacity = 1; loader.x = 0 }

      Loader {
        id: loader
        width: parent.width
        height: parent.height
        source: content.shownSource
        // Re-hand the notch if the root item is replaced.
        onLoaded: if (item) item.notch = panel.notch
        Connections {
          target: panel
          function onNotchChanged() { if (loader.item) loader.item.notch = panel.notch }
        }
      }
      SequentialAnimation {
        id: swapAnim
        ParallelAnimation {
          NumberAnimation { target: loader; property: "opacity"; to: 0; duration: panel.reduce ? Motion.REDUCED_FADE_MS / 2 : Motion.TAB_OUT_MS; easing.type: Easing.OutQuad }
          NumberAnimation { target: loader; property: "x"; to: panel.reduce ? 0 : -content.dir * Motion.TAB_SHIFT_OUT; duration: Motion.TAB_OUT_MS; easing.type: Easing.OutQuad }
        }
        ScriptAction { script: { content.shownSource = content.wantSource; content.shownIndex = content.wantIndex; loader.x = panel.reduce ? 0 : content.dir * Motion.TAB_SHIFT_IN } }
        ParallelAnimation {
          NumberAnimation { target: loader; property: "opacity"; to: 1; duration: panel.reduce ? Motion.REDUCED_FADE_MS / 2 : Motion.TAB_IN_MS; easing.type: Easing.OutQuad }
          NumberAnimation { target: loader; property: "x"; to: 0; duration: panel.reduce ? 1 : Motion.TAB_IN_MS; easing.type: Easing.OutCubic }
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
