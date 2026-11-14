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
// with a Loader; the loaded item gets `notch` set to the root Island.qml item.
// A tab whose file does not exist yet shows a quiet "coming soon" line.
// Opaque cover fades in with `progress` so the idle row gives way to it.
Item {
  id: panel

  property bool active: false          // island is open
  property real progress: 0            // 0 collapsed .. 1 expanded
  property int headerHeight: 32
  property var notch: null             // root Island.qml item, handed to every tab
  property var weather: null           // Model.parseWeather output
  property color islandColor: notch ? notch.islandColor : Tk.black
  property color textColor: notch ? notch.textColor : Tk.text
  property color dimColor: notch ? notch.dimColor : Tk.dim
  property string family: notch ? notch.fontFamily : Commons.Style.font.family
  readonly property var themeObj: notch && notch.themeObj ? notch.themeObj : Theme.resolve("swift")
  property date now: new Date()

  property string currentTab: Tabs.DEFAULT_TAB   // owned by the window (it sizes the panel); bound by the Loader
  signal tabSelected(string id)
  readonly property var tabs: Tabs.visibleTabs(notch ? notch.settings : null, undefined, notch ? notch.capabilities : null)
  readonly property var tab: Tabs.select(currentTab, tabs)
  readonly property string pluginDir: notch ? notch.pluginDir : ""

  // Keyboard: Ctrl+Tab / Ctrl+Shift+Tab cycle the visible tabs (hidden ones are skipped).
  Shortcut { sequence: "Ctrl+Tab"; enabled: panel.active; onActivated: panel.tabSelected(Tabs.cycle(panel.tabs, panel.tab.id, 1)) }
  Shortcut { sequence: "Ctrl+Shift+Tab"; enabled: panel.active; onActivated: panel.tabSelected(Tabs.cycle(panel.tabs, panel.tab.id, -1)) }

  // tab id -> true/false once its source file has been probed.
  property var sourceExists: ({})
  readonly property bool reduce: notch ? notch.reduceMotion : Commons.Style.reduceMotion
  readonly property var resolved: Tabs.resolve(tab, sourceExists)

  Rectangle {
    anchors.fill: parent
    color: panel.islandColor
    opacity: Math.min(1, panel.progress * 1.6)
    visible: !Tk.pxl
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
    // Glyph chips; the selected tab and the two most-opened ones also show
    // their label (all of them when everything fits). Chip geometry comes from
    // Tabs.stripLayout using measured label widths, so nothing truncates.
    SpringValue { id: indX; target: strip.lay.xs.length > strip.selIndex ? strip.lay.xs[strip.selIndex] : 0; instant: panel.reduce; stepped: Tk.pxl; duration: Motion.STRIP.duration; bounce: Motion.STRIP.bounce }
    SpringValue { id: indW; target: strip.lay.widths.length > strip.selIndex ? strip.lay.widths[strip.selIndex] : 0; instant: panel.reduce; stepped: Tk.pxl; duration: Motion.STRIP.duration; bounce: Motion.STRIP.bounce }
    Rectangle {
      x: strip.x + indX.value; y: strip.y; width: indW.value; height: strip.height; radius: Tk.r(height / 2)
      color: Tk.tint(0.16)
    }

    // Tiny theme switch: flips swift <-> pxl instantly and persists it.
    Rectangle {
      id: themeToggle
      anchors.top: parent.top
      anchors.right: parent.right
      width: 26; height: 26
      radius: Tk.r(13)
      color: tgHit.containsMouse ? Tk.tint(0.16) : Tk.tint(0.08)
      border.width: Tk.pxl ? Tk.bw(1) : 0
      border.color: Tk.edge
      Text {
        anchors.centerIn: parent
        textFormat: Text.PlainText
        text: Tk.pxl ? "\u25A3" : "\u25EF"
        color: Tk.pxl ? Tk.accent : panel.dimColor
        font.pixelSize: 14
      }
      MouseArea {
        id: tgHit
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (panel.notch) panel.notch.toggleTheme()
      }
    }

    Item {
      id: strip
      anchors.top: parent.top
      anchors.left: parent.left
      anchors.right: themeToggle.left
      anchors.rightMargin: 6
      height: 26

      readonly property int gap: 4
      readonly property int glyphW: 12
      readonly property int padX: 10
      readonly property var ids: panel.tabs.map(function (t) { return t.id })
      readonly property int selIndex: { for (var i = 0; i < panel.tabs.length; i++) if (panel.tabs[i].id === panel.tab.id) return i; return 0 }
      readonly property var usage: panel.notch && panel.notch.settings ? panel.notch.settings.tabUsage : null
      readonly property var lay: Tabs.stripLayout(ids, Tabs.labelIds(panel.tabs, panel.tab.id, usage), labelW, width, gap, glyphW, padX)

      // Measured label widths by tab id (updated as fonts load).
      property var labelW: ({})
      function setW(id, w) {
        if (labelW[id] === w) return
        var copy = {}
        for (var k in labelW) copy[k] = labelW[k]
        copy[id] = w
        labelW = copy
      }
      Repeater {
        model: Tabs.TABS
        Item {
          required property var modelData
          TextMetrics {
            font.family: Tk.label
            font.pixelSize: Tk.fs.caption
            text: modelData.short || modelData.title
            onAdvanceWidthChanged: strip.setW(modelData.id, advanceWidth)
            Component.onCompleted: strip.setW(modelData.id, advanceWidth)
          }
        }
      }

      Repeater {
        model: panel.tabs
        Rectangle {
          id: chip
          required property var modelData
          required property int index
          readonly property bool selected: chip.modelData.id === panel.tab.id
          readonly property bool showLabel: strip.lay.labeled[chip.modelData.id] === true
          x: index < strip.lay.xs.length ? strip.lay.xs[index] : 0
          width: index < strip.lay.widths.length ? strip.lay.widths[index] : 0
          height: strip.height
          radius: Tk.r(height / 2)
          color: !selected && hit.containsMouse ? Tk.tint(0.08) : "transparent"

          Row {
            anchors.centerIn: parent
            spacing: 4
            Text {
              textFormat: Text.PlainText
              text: chip.modelData.glyph
              color: chip.selected ? panel.textColor : panel.dimColor
              font.family: panel.family
              font.pixelSize: Tk.fs.bodySmall
              anchors.verticalCenter: parent.verticalCenter
            }
            Text {
              visible: chip.showLabel
              textFormat: Text.PlainText
              text: chip.modelData.short || chip.modelData.title
              color: chip.selected ? panel.textColor : panel.dimColor
              font.family: Tk.label
              font.pixelSize: Tk.fs.caption
              anchors.verticalCenter: parent.verticalCenter
            }
          }
          MouseArea {
            id: hit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPressed: panel.tabSelected(chip.modelData.id)
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
        font.pixelSize: Tk.fs.bodySmall
      }
    }
  }
}
