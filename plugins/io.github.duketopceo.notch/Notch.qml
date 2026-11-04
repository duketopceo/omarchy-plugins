import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import qs.Commons as Commons
import "Model.js" as Model

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

  // Settings (v0.1: constants; later read from the plugin's shell.json entry).
  readonly property int cameraWidth: 200   // logical px, 14"/16" MacBook Pro
  readonly property int earWidth: 96       // content room either side of the camera
  readonly property int virtualWidth: 300  // island width on screens without a cutout
  readonly property int clockSeconds: 24
  readonly property int slideSeconds: 7

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

  property var weather: null
  FileView {
    id: cacheFile
    path: Quickshell.env("HOME") + "/.cache/omarchy/notch.json"
    watchChanges: true
    printErrors: false
    onLoaded: root.weather = Model.parseWeather(text())
    onLoadFailed: root.weather = null
    onFileChanged: reload()
  }

  Process {
    id: fetcher
    command: [root.pluginDir + "/bin/notch-data", "--max-age", "900"]
    onExited: cacheFile.reload()
  }
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

  readonly property string timeText: Qt.formatTime(now, "h:mm AP")
  readonly property string dateText: Qt.formatDate(now, "ddd d MMM")
  // Now playing takes over the side text while a player is playing.
  readonly property var player: {
    var list = Mpris.players ? Mpris.players.values : []
    for (var i = 0; i < list.length; i++) if (list[i] && list[i].isPlaying) return list[i]
    return null
  }
  readonly property string mediaText: player ? "\u{F075A} " + String(player.trackTitle || player.identity || "") : ""

  readonly property string view: player ? "media" : Model.idleView(now.getTime() / 1000, weather ? ["weather"] : [], clockSeconds, slideSeconds)
  readonly property string weatherText: weather ? weather.temperature + weather.unit : ""
  readonly property string sideText: view === "media" ? mediaText : (view === "weather" ? weatherText : dateText)
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

      anchors { top: true; left: true; right: true }
      implicitHeight: island.height
      color: "transparent"
      WlrLayershell.namespace: "omarchy-notch"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      mask: Region { item: island }

      Rectangle {
        id: island
        width: win.notched ? root.cameraWidth + 2 * root.earWidth : root.virtualWidth
        height: win.notched ? Math.max(win.cut, root.barHeight) : root.barHeight
        x: Math.round((parent.width - width) / 2)
        y: 0
        color: root.islandColor
        topLeftRadius: 0
        topRightRadius: 0
        bottomLeftRadius: Math.round(height * 0.45)
        bottomRightRadius: Math.round(height * 0.45)

        // Notched: time in the left ear, date/weather in the right ear.
        Text {
          visible: win.notched
          anchors.verticalCenter: parent.verticalCenter
          x: Math.round((root.earWidth - width) / 2)
          text: root.timeText
          color: root.textColor
          font.family: root.fontFamily
          font.pixelSize: 13
          font.weight: Font.DemiBold
        }
        SlideText {
          visible: win.notched
          anchors.verticalCenter: parent.verticalCenter
          x: root.earWidth + root.cameraWidth + Math.round((root.earWidth - width) / 2)
          target: root.sideText
          iconKind: root.weather ? root.weather.kind : ""
          iconOn: root.showIcon
          maxWidth: root.earWidth - 8
          color: root.view === "date" || root.view === "clock" ? root.dimColor : root.textColor
          family: root.fontFamily
        }

        // Virtual notch: one centered line.
        Row {
          visible: !win.notched
          anchors.centerIn: parent
          spacing: 10
          Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.timeText
            color: root.textColor
            font.family: root.fontFamily
            font.pixelSize: 13
            font.weight: Font.DemiBold
          }
          SlideText {
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
