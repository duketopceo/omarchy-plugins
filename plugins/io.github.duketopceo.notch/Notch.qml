import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import qs.Commons as Commons
import "Model.js" as Model
import "Watchlist.js" as Watchlist
import "Expand.js" as Expand  // U5 hover expand
import "Settings.js" as Settings
import "Activity.js" as Activity
import "Plugins.js" as Plugins

// Notch island: one small layer-shell window per screen at top center.
// On a panel with a camera cutout (Omarchy's display-cutouts.json) it hugs
// the camera and uses the space either side of it; elsewhere it is a
// virtual notch. Idle content: clock and date, with weather sliding in.
Item {
  id: root

  // Injected by the shell's panel loader.
  property var shell: null
  property var manifest: null

  readonly property string pluginDir: {
    var p = Qt.resolvedUrl(".").toString()
    if (p.indexOf("file://") === 0) p = p.substring(7)
    if (p.length > 1 && p.charAt(p.length - 1) === "/") p = p.substring(0, p.length - 1)
    return p
  }

  // ------------------------------------------------------------ settings
  // Stored in this plugin's entry of shell.json (`plugins[]`), edited from the
  // Settings tab. Missing or invalid values fall back to Settings.DEFAULTS.

  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.duketopceo.notch"

  // The injected shell config when present, else shell.json read directly.
  property var fileConfig: null
  FileView {
    id: shellJson
    path: Quickshell.env("HOME") + "/.config/omarchy/shell.json"
    watchChanges: true
    printErrors: false
    onLoaded: { try { root.fileConfig = JSON.parse(text()) } catch (e) { root.fileConfig = null } }
    onLoadFailed: root.fileConfig = null
    onFileChanged: reload()
  }
  readonly property var shellConfig: shell && shell.shellConfig ? shell.shellConfig : fileConfig

  // Values just set from the UI, so they show even before the config reloads.
  property var pending: ({})
  readonly property var settings: Settings.resolve(Settings.pluginEntry(shellConfig, pluginId), pending)

  function setSetting(key, value) {
    var copy = {}
    for (var k in pending) copy[k] = pending[k]
    copy[key] = value
    pending = copy
    if (!shell || typeof shell.mutateShellConfig !== "function") return
    var patch = {}
    patch[key] = value
    shell.mutateShellConfig(Settings.settingsMutator(pluginId, patch))
  }

  // Open a plugin's panel: the shell's in-process toggle, else `qs ipc`.
  function openPlugin(id) {
    if (shell && typeof shell.toggle === "function") shell.toggle(String(id), "{}")
    else Quickshell.execDetached(Plugins.ipcCommand(id))
  }

  readonly property int autoCameraWidth: 200   // logical px, 14"/16" MacBook Pro
  readonly property int cameraWidth: settings.cameraWidth > 0 ? settings.cameraWidth : autoCameraWidth
  readonly property int earWidth: 96       // content room either side of the camera
  // Camera width override from Settings (0 = auto-detect from the device model).
  readonly property int cameraOverride: settings.cameraWidth > 0 ? settings.cameraWidth : 0
  readonly property int virtualWidth: 300  // island width on screens without a cutout
  readonly property int clockSeconds: settings.clockSeconds
  readonly property int slideSeconds: settings.slideSeconds

  readonly property color islandColor: "black"
  readonly property color textColor: Commons.Color.foreground
  readonly property color dimColor: Commons.Color.muted
  readonly property string fontFamily: Commons.Style.font.family
  readonly property int barHeight: Commons.Style.bar && Commons.Style.bar.sizeHorizontal > 0 ? Commons.Style.bar.sizeHorizontal : 32

  // ------------------------------------------------------------ data

  property var cutouts: Model.parseCutouts(cutoutFile.text())
  FileView {
    id: cutoutFile
    path: "/usr/share/omarchy-platform/display-cutouts.json"
    blockLoading: true
    printErrors: false
    onLoaded: root.cutouts = Model.parseCutouts(text())
    onLoadFailed: root.cutouts = []
  }

  // Device model from the device tree (NUL-separated compatible strings).
  property string deviceCompatible: ""
  FileView {
    id: compatFile
    path: "/proc/device-tree/compatible"
    blockLoading: true
    printErrors: false
    onLoaded: root.deviceCompatible = text()
    onLoadFailed: root.deviceCompatible = ""
  }

  property var weather: null
  property var quotes: []  // watchlist hook: from the cache "quotes" key
  FileView {
    id: cacheFile
    path: Quickshell.env("HOME") + "/.cache/omarchy/notch.json"
    watchChanges: true
    printErrors: false
    onLoaded: { root.weather = Model.parseWeather(text()); root.quotes = Watchlist.parseQuotes(text()) }  // watchlist hook
    onLoadFailed: root.weather = null
    onFileChanged: reload()
  }

  Process {
    id: fetcher
    command: [root.pluginDir + "/bin/notch-data"].concat(Settings.dataArgs(root.settings))
    onExited: cacheFile.reload()
  }
  // A new temperature unit refetches (the cache is keyed on the unit).
  readonly property string unitName: settings.unitName
  onUnitNameChanged: if (!fetcher.running) fetcher.running = true
  Timer {
    interval: 10 * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: if (!fetcher.running) fetcher.running = true
  }

  property date now: new Date()
  Timer {
    interval: 1000
    running: true
    repeat: true
    onTriggered: root.now = new Date()
  }

  readonly property string timeText: Qt.formatTime(now, settings.timeFormat)
  readonly property string dateText: Qt.formatDate(now, "ddd d MMM")
  // Now playing (N3): MediaActivity picks the player (fastpotify, then Spotify,
  // then any playing MPRIS player). Registered in `activities` below.
  MediaActivity { id: media }
  readonly property var mediaActivity: media   // read by MediaTab.qml
  readonly property var player: media.active ? media.player : null
  readonly property string mediaText: media.active ? media.text : ""
  readonly property bool mediaShown: activity !== null && activity !== undefined && activity.id === "media"
  readonly property int eqSpace: mediaShown ? 14 : 0   // room for the equalizer glyph

  // WordInk dictation (U4): follows `wordink logs -f`; takes over the side text.
  WordinkActivity { id: dictation }

  // Blip iMessage (N5): read-only. Flashes for allowlisted senders; MessagesTab reads `notch.messages`.
  MessagesActivity { id: messagesAct }
  readonly property var messages: messagesAct

  // Agents (N4): herdr agent status. AgentsTab reads it via `agentsActivity`.
  AgentsActivity { id: agents }
  readonly property var agentsActivity: agents

  // Activity contract: each entry is { id, active, priority, text, glyph? }.
  // The side text shows the highest-priority active one (ties: first listed),
  // else the idle cycle. Add a new XActivity as one more line, anywhere in
  // the list; order does not matter beyond ties.
  readonly property var activities: [
    { id: "dictation", active: dictation.active, priority: 90, text: dictation.text },
    { id: "media", active: media.active, priority: 50, text: media.text, glyph: media.glyph },
    { id: "agents", active: agents.active, priority: agents.priority, text: agents.text, glyph: agents.glyph },
    { id: "messages", active: messagesAct.active, priority: messagesAct.priority, text: messagesAct.text, glyph: messagesAct.glyph }
    // activities:end
  ]
  readonly property var activity: Activity.pick(activities)

  readonly property string idleView: Model.idleView(now.getTime() / 1000, (weather && settings.showWeather ? ["weather"] : []).concat(quotes.length && settings.showStocks ? ["watchlist"] : []), clockSeconds, slideSeconds)  // watchlist hook: "watchlist" idle view when quotes exist
  readonly property string view: activity ? "activity" : idleView
  readonly property string weatherText: weather ? weather.temperature + weather.unit : ""
  readonly property string sideText: activity ? Activity.label(activity) : (idleView === "weather" ? weatherText : dateText)
  readonly property bool showIcon: view === "weather" && weather !== null

  // ------------------------------------------------------------ windows

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: win
      required property var modelData
      screen: modelData

      readonly property var monitor: Hyprland.monitorFor(modelData)
      readonly property int cut: monitor ? Model.cutoutTop(root.cutouts, modelData.name, modelData.width, {
        width: monitor.width,
        height: monitor.height,
        transform: monitor.lastIpcObject ? monitor.lastIpcObject.transform : 0
      }) : 0
      readonly property bool notched: cut > 0
      readonly property int camW: Model.cameraWidthFor(root.deviceCompatible, monitor ? monitor.width : 0, modelData.width, root.cameraOverride) || Model.SIZES.cameraWidth
      readonly property int earW: Model.earWidthFor(modelData.width)

      // --- U5 hover expand (state machine in Expand.js, UI in ExpandedPanel.qml) ---
      property string xstate: "collapsed"
      readonly property bool expanded: Expand.isExpanded(xstate)
      readonly property int baseWidth: notched ? camW + 2 * earW : root.virtualWidth
      readonly property int baseHeight: notched ? Math.max(cut, root.barHeight) : root.barHeight
      readonly property var panelSz: Expand.panelSize(modelData.width)
      function xevent(e) {
        var r = Expand.step(xstate, e, root.settings.hoverDelay)
        xstate = r.state
        if (r.timer > 0) { xtimer.interval = r.timer; xtimer.restart() } else xtimer.stop()
      }
      Timer { id: xtimer; onTriggered: win.xevent("timer") }
      // --- end U5 ---

      anchors { top: true; left: true; right: true }
      // Window stays tall while expanded or still animating; the mask below is what takes input.
      implicitHeight: expanded || island.height > baseHeight ? panelSz.height + 16 : island.height
      color: "transparent"
      WlrLayershell.namespace: "omarchy-notch"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      mask: Region { item: island }

      Rectangle {
        id: island
        width: win.expanded ? win.panelSz.width : win.baseWidth     // U5
        height: win.expanded ? win.panelSz.height : win.baseHeight  // U5
        Behavior on width { NumberAnimation { duration: 340; easing.type: Easing.OutBack; easing.overshoot: 1.1 } }   // U5
        Behavior on height { NumberAnimation { duration: 340; easing.type: Easing.OutBack; easing.overshoot: 1.1 } }  // U5
        x: Math.round((parent.width - width) / 2)
        y: 0
        color: root.islandColor
        topLeftRadius: 0
        topRightRadius: 0
        bottomLeftRadius: Math.min(24, Math.round(height * 0.45))
        bottomRightRadius: Math.min(24, Math.round(height * 0.45))

        // U5: hover opens the panel; keyboard focus stays None (see window above).
        HoverHandler { onHoveredChanged: win.xevent(hovered ? "enter" : "leave") }
        Loader {
          anchors.fill: parent
          z: 1
          active: win.expanded || island.height > win.baseHeight + 1
          sourceComponent: ExpandedPanel {
            active: win.expanded
            progress: Math.max(0, Math.min(1, (island.height - win.baseHeight) / (win.panelSz.height - win.baseHeight)))
            headerHeight: win.baseHeight
            notch: root
            weather: root.weather
            now: root.now
            islandColor: root.islandColor
            textColor: root.textColor
            dimColor: root.dimColor
            family: root.fontFamily
          }
        }

        // Notched: time in the left ear, date/weather in the right ear.
        Text {
          visible: win.notched
          anchors.verticalCenter: parent.verticalCenter
          x: Math.round((win.earW - width) / 2)
          text: root.timeText + (agents.badge ? "  " + agents.badge : "")
          color: root.textColor
          font.family: root.fontFamily
          font.pixelSize: 13
          textFormat: Text.PlainText
          font.weight: Font.DemiBold
        }
        // watchlist hook: the slide replaces the side text while view === "watchlist".
        WatchlistSlide {
          visible: win.notched && root.view === "watchlist"
          anchors.verticalCenter: parent.verticalCenter
          x: win.earW + win.camW + Math.round((win.earW - width) / 2)
          quotes: root.quotes
          index: Math.floor(root.now.getTime() / 1000 / (root.clockSeconds + 2 * root.slideSeconds))
          notched: true
          maxWidth: win.earW - 8
          family: root.fontFamily
        }
        SlideText {
          visible: win.notched && root.view !== "watchlist"
          anchors.verticalCenter: parent.verticalCenter
          x: win.earW + win.camW + root.eqSpace + Math.round((win.earW - root.eqSpace - width) / 2)
          target: root.sideText
          iconKind: root.weather ? root.weather.kind : ""
          iconOn: root.showIcon
          maxWidth: win.earW - 8 - root.eqSpace
          color: root.view === "date" || root.view === "clock" ? root.dimColor : root.textColor
          family: root.fontFamily
        }

        // N3: animated equalizer beside the title while media plays.
        EqGlyph {
          visible: win.notched && root.mediaShown
          playing: media.active
          color: root.textColor
          anchors.verticalCenter: parent.verticalCenter
          x: root.earWidth + root.cameraWidth + 4
        }

        // WordInk dictation dot (U4): pulses while recording.
        WordinkDot {
          activity: dictation
          anchors.verticalCenter: parent.verticalCenter
          anchors.right: parent.right
          anchors.rightMargin: Math.round(parent.height * 0.45)
        }

        // Virtual notch: one centered line.
        Row {
          visible: !win.notched
          anchors.centerIn: parent
          spacing: 10
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.timeText + (agents.badge ? "  " + agents.badge : "")
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: 13
            textFormat: Text.PlainText
            font.weight: Font.DemiBold
          }
          EqGlyph {
            visible: root.mediaShown
            playing: media.active
            color: root.textColor
            anchors.verticalCenter: parent.verticalCenter
          }
          // watchlist hook (virtual notch).
          WatchlistSlide {
            visible: root.view === "watchlist"
            anchors.verticalCenter: parent.verticalCenter
            quotes: root.quotes
            index: Math.floor(root.now.getTime() / 1000 / (root.clockSeconds + 2 * root.slideSeconds))
            notched: false
            maxWidth: root.virtualWidth - 110
            family: root.fontFamily
          }
          SlideText {
            visible: root.view !== "watchlist"
            anchors.verticalCenter: parent.verticalCenter
            target: root.sideText
            iconKind: root.weather ? root.weather.kind : ""
            iconOn: root.showIcon
            maxWidth: root.virtualWidth - 110
            color: root.view === "date" || root.view === "clock" ? root.dimColor : root.textColor
            family: root.fontFamily
          }
        }
      }
    }
  }

  // A label that slides up and fades when its text changes.
  component SlideText: Item {
    id: slide
    property string target: ""
    property string iconKind: ""     // pixel-art weather icon shown before the text
    property bool iconOn: false
    property color color: "white"
    property string family: ""
    property string shown: ""
    property int maxWidth: 10000
    property int iconSpace: iconOn ? icon.width + 4 : 0
    Behavior on iconSpace { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }
    implicitWidth: Math.min(maxWidth, label.implicitWidth + iconSpace)
    implicitHeight: label.implicitHeight
    width: implicitWidth
    height: implicitHeight
    clip: false

    Component.onCompleted: shown = target
    onTargetChanged: if (target !== shown) swap.restart()

    PixelWeather {
      id: icon
      kind: slide.iconKind || "cloudy"
      active: slide.iconOn
      anchors.verticalCenter: parent.verticalCenter
      opacity: slide.iconOn ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 220 } }
    }

    Text {
      id: label
      x: slide.iconSpace
      width: slide.width - slide.iconSpace
      text: slide.shown
      color: slide.color
      font.family: slide.family
      font.pixelSize: 13
      textFormat: Text.PlainText
      elide: Text.ElideRight
    }

    SequentialAnimation {
      id: swap
      ParallelAnimation {
        NumberAnimation { target: label; property: "opacity"; to: 0; duration: 160; easing.type: Easing.InQuad }
        NumberAnimation { target: label; property: "y"; to: -6; duration: 160; easing.type: Easing.InQuad }
      }
      ScriptAction { script: { slide.shown = slide.target; label.y = 6 } }
      ParallelAnimation {
        NumberAnimation { target: label; property: "opacity"; to: 1; duration: 220; easing.type: Easing.OutQuad }
        NumberAnimation { target: label; property: "y"; to: 0; duration: 220; easing.type: Easing.OutQuad }
      }
    }
  }
}
