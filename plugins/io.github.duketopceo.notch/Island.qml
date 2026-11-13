import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Commons as Commons
import "Model.js" as Model
import "Settings.js" as Settings
import "IslandActivity.js" as Island
import "Motion.js" as Motion
import "Plugins.js" as Plugins

// Island: the notch's primary surface. Compact shows the clock and up to two
// live activities either side of the camera; expanded shows controls for the
// activity that is showing. Replaces the dashboard as what a glance reveals;
// the dashboard stays reachable behind an explicit control (R6, KTD8).
//
// The five collectors are the existing ones, unchanged (KTD2). Selection is
// pure logic in IslandActivity.js so it can be tested with node (KTD3).
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

  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.duketopceo.notch"

  // ------------------------------------------------------------ settings
  // Same read path as Notch.qml: the injected shell config when present, else
  // shell.json read directly. Missing or invalid values fall back to DEFAULTS.
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
  property var pending: ({})
  readonly property var settings: Settings.resolve(Settings.pluginEntry(shellConfig, pluginId), pending)

  readonly property color islandColor: "black"
  readonly property string fontFamily: Commons.Style.font.family
  readonly property int barHeight: Commons.Style.bar && Commons.Style.bar.sizeHorizontal > 0 ? Commons.Style.bar.sizeHorizontal : 32
  readonly property bool reduceMotion: Commons.Style.reduceMotion || (settings && settings.reduceMotion === true)

  // ------------------------------------------------------------ cutouts
  property var cutouts: []
  FileView {
    id: cutoutFile
    path: "/usr/share/omarchy-platform/display-cutouts.json"
    watchChanges: false
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
  readonly property int cameraOverride: settings.cameraWidth > 0 ? settings.cameraWidth : 0
  readonly property int virtualWidth: 300
  readonly property int earPad: 6
  readonly property int earMargin: 12

  // ------------------------------------------------------------ collectors
  // The same five entries Notch.qml builds, in the same shape: each activity is
  // { id, active, priority, text, glyph? } (KTD2: no parallel collectors).
  MediaActivity { id: media }
  WordinkActivity { id: dictation }
  readonly property bool wordinkOn: settings.optWordink !== false
  MessagesActivity { id: messagesAct }
  AgentsActivity { id: agents; enabled: root.settings.optAgents === true }
  ScreenshotsActivity { id: shots; enabled: root.settings.snapdex }

  readonly property var activities: [
    { id: "dictation", active: wordinkOn && dictation.active, priority: 90, text: dictation.text },
    { id: "media", active: media.active, priority: 50, text: media.text, glyph: media.glyph },
    { id: "agents", active: agents.active, priority: agents.priority, text: agents.text, glyph: agents.glyph },
    { id: "messages", active: root.settings.optMessages === true && messagesAct.active, priority: messagesAct.priority, text: messagesAct.text, glyph: messagesAct.glyph },
    { id: "screenshots", active: root.settings.snapdex && shots.active, priority: shots.priority, text: shots.text, glyph: shots.glyph }
  ]

  readonly property var ranked: Island.visible(activities)

  property date now: new Date()
  // True while any screen's island is expanded; media position only needs
  // ticking then. Set by each window, since `win` is not visible from here.
  property bool anyExpanded: false
  Timer {
    interval: 1000
    running: true
    repeat: true
    onTriggered: {
      root.now = new Date()
      if (root.anyExpanded && media.player) media.player.positionChanged()
    }
  }

  readonly property string timeText: Qt.formatTime(now, settings.timeFormat)
  readonly property string dateText: Qt.formatDate(now, "ddd d MMM")

  // ------------------------------------------------------------ IPC (R5)
  // `qs ipc call notch open` focuses the Island for keyboard use; `close`
  // dismisses it. openTab/closeTab keep the dashboard route working.
  signal dismissRequested()
  signal openRequested()
  signal dashboardRequested()
  IpcHandler {
    target: "notch"
    function open(): void { root.openRequested() }
    function close(): void { root.dismissRequested() }
    function dashboard(): void { root.dashboardRequested() }
  }

  function primaryScreenName() {
    var list = Quickshell.screens || []
    for (var i = 0; i < list.length; i++) if (list[i].name === "eDP-1") return list[i].name
    return list.length ? list[0].name : ""
  }

  // Opening the dashboard is a deliberate act (KTD8); it goes through the
  // plugin's own open chain rather than assuming separate bar widgets exist.
  property var openSteps: []
  property int openIndex: 0
  function openDashboard() {
    if (opener.running) return
    openSteps = Plugins.openChain(pluginId, null)
    openIndex = 0
    runOpenStep()
  }
  function runOpenStep() {
    if (openIndex >= openSteps.length) return
    opener.command = openSteps[openIndex].cmd
    opener.running = true
  }
  Process {
    id: opener
    stdout: StdioCollector { id: openerOut }
    onExited: function (code) {
      if (Plugins.stepOk(root.openSteps[root.openIndex], code, openerOut.text)) return
      root.openIndex += 1
      root.runOpenStep()
    }
  }

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
      readonly property int camW: Model.cameraWidthFor(root.deviceCompatible, monitor ? monitor.width : 0, modelData.width, root.cameraOverride, cut) || Model.SIZES.cameraWidth
      // The prototype's calibration: the internal panel is the widest camera
      // on omarchy-max; an external panel gets a narrower virtual notch.
      readonly property int sensorWidth: modelData.name === "eDP-1" ? Math.max(186, camW) : 95

      // Expanded geometry from the prototype (KTD3).
      readonly property int compactWidth: Math.max(250, sensorWidth + 120)
      readonly property int compactHeight: 37
      readonly property int expandedWidth: 374
      readonly property int expandedHeight: 180

      property bool expanded: false
      // The activity the expanded view is about. Held by id, never by rank, so
      // a reorder cannot move a control onto a different activity (KTD6).
      property string selectedId: ""

      readonly property var ranked: root.ranked
      readonly property var selected: Island.selected(ranked, selectedId)
      readonly property var segments: {
        if (!Island.canSplit(compactWidth, sensorWidth + 40, 70, ranked.length > 1 ? 70 : 0)) return ranked.slice(0, 1)
        return ranked.slice(0, 2)
      }

      function openIsland(id) {
        selectedId = id
        expanded = true
      }
      function closeIsland() {
        expanded = false
      }
      // When the selected activity ends, keep the window but show a neutral
      // state instead of another activity's controls (KTD6).
      onRankedChanged: {
        if (expanded && selectedId !== "" && Island.selected(ranked, selectedId) === null) selectedId = ""
      }
      onExpandedChanged: root.anyExpanded = expanded

      Connections {
        target: root
        function onDismissRequested() { win.closeIsland() }
        function onOpenRequested() {
          if (modelData.name !== root.primaryScreenName()) return
          if (win.selectedId === "" && win.ranked.length) win.selectedId = win.ranked[0].id
          win.expanded = true
        }
        function onDashboardRequested() { root.openDashboard() }
      }

      HyprlandFocusGrab {
        active: win.expanded
        windows: [win]
        onCleared: win.closeIsland()
      }

      anchors.top: true
      implicitWidth: expandedWidth + 40
      implicitHeight: expanded ? expandedHeight + 20 : compactHeight + 20
      color: "transparent"
      WlrLayershell.namespace: "omarchy-notch-island"
      WlrLayershell.layer: WlrLayer.Overlay
      // Keyboard focus only once opened, so hover never steals it (R5).
      WlrLayershell.keyboardFocus: win.expanded ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None
      exclusionMode: ExclusionMode.Ignore
      mask: Region { item: island }

      Rectangle {
        id: island
        anchors.horizontalCenter: parent.horizontalCenter
        width: win.expanded ? win.expandedWidth : win.compactWidth
        height: win.expanded ? win.expandedHeight : win.compactHeight
        radius: win.expanded ? 46 : 18.5
        color: root.islandColor
        clip: true
        Accessible.role: Accessible.Pane
        Accessible.name: win.expanded ? qsTr("Notch island, expanded") : qsTr("Notch island")

        // Reduced motion snaps the shape; the content still cross-fades (R4).
        Behavior on width { enabled: !root.reduceMotion; NumberAnimation { duration: 390; easing.type: Easing.OutBack; easing.overshoot: 0.45 } }
        Behavior on height { enabled: !root.reduceMotion; NumberAnimation { duration: 390; easing.type: Easing.OutBack; easing.overshoot: 0.3 } }
        Behavior on radius { enabled: !root.reduceMotion; NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

        Shortcut { sequence: "Escape"; enabled: win.expanded; onActivated: win.closeIsland() }

        // ---------------------------------------------------------- compact
        Item {
          anchors.fill: parent
          opacity: win.expanded ? 0 : 1
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: root.reduceMotion ? 0 : 120; easing.type: Easing.OutCubic } }

          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: 8
            width: Math.max(0, (parent.width - win.sensorWidth) / 2 - 14)
            horizontalAlignment: Text.AlignRight
            text: root.timeText
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: "#f8f8f8"
            font.family: root.fontFamily
            font.pixelSize: 13
            font.weight: Font.DemiBold
          }

          // Right ear: the top-ranked activity, else the date. This is the
          // compact half of R1; the second segment lives here too when space
          // allows (segments is capped by canSplit).
          Text {
            anchors.verticalCenter: parent.verticalCenter
            x: (parent.width + win.sensorWidth) / 2 + 6
            width: Math.max(0, parent.width - x - 8)
            text: {
              // Message and screenshot text is externally sourced; PlainText
              // keeps markup inert (KTD7).
              if (win.segments.length > 0) {
                var a = win.segments[0]
                var second = win.segments.length > 1 ? "  ·  " + win.segments[1].text : ""
                return (a.glyph ? a.glyph + " " : "") + a.text + second
              }
              return root.dateText
            }
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: "#e6e6e6"
            font.family: root.fontFamily
            font.pixelSize: 12
            Accessible.role: Accessible.StaticText
            Accessible.name: win.segments.length ? win.segments[0].text : root.dateText
          }

          TapHandler {
            enabled: !win.expanded
            onTapped: win.openIsland(win.ranked.length ? win.ranked[0].id : "")
          }
        }

        // ---------------------------------------------------------- expanded
        Item {
          anchors.fill: parent
          opacity: win.expanded ? 1 : 0
          visible: opacity > 0
          Behavior on opacity { NumberAnimation { duration: root.reduceMotion ? 0 : 180; easing.type: Easing.OutCubic } }

          // Neutral state: the activity that was showing has ended.
          Text {
            anchors.centerIn: parent
            visible: win.expanded && win.selected === null
            text: qsTr("Nothing active")
            textFormat: Text.PlainText
            color: "#8f8f8f"
            font.family: root.fontFamily
            font.pixelSize: 13
          }

          // Per-activity detail. Each control is bound to its own id, so a
          // reorder cannot move it (KTD6).
          Item {
            anchors.fill: parent
            visible: win.selected !== null

            // Media: artwork, title, artist, progress, transport.
            Item {
              id: mediaView
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "media"

              Rectangle {
                id: artwork
                x: 22; y: 41; width: 60; height: 60; radius: 13
                color: "#282828"
                Image {
                  anchors.fill: parent
                  source: media.player && media.player.trackArtUrl ? media.player.trackArtUrl : ""
                  fillMode: Image.PreserveAspectCrop
                  asynchronous: true
                  visible: status === Image.Ready
                }
                Text {
                  anchors.centerIn: parent
                  visible: !media.player || !media.player.trackArtUrl
                  text: "♫"
                  textFormat: Text.PlainText
                  color: "#a6a6a6"
                  font.pixelSize: 25
                }
              }
              Text {
                x: 98; y: 44; width: parent.width - x - 26
                text: win.selected !== null ? win.selected.text : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: "#ffffff"
                font.family: root.fontFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
              }
              Text {
                x: 98; y: 66; width: parent.width - x - 26
                text: media.player ? (media.player.trackArtist || media.player.identity) : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: "#a4a4a4"
                font.family: root.fontFamily
                font.pixelSize: 13
              }
              Rectangle {
                x: 23; y: 112; width: parent.width - 46; height: 4; radius: 2
                color: "#393939"
                visible: !!media.player && media.player.length > 0
                Rectangle {
                  width: parent.width * Math.max(0, Math.min(1, media.player ? media.player.position / media.player.length : 0))
                  height: parent.height
                  radius: 2
                  color: "#f1f1f1"
                }
              }
              Row {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 129
                spacing: 38
                visible: !!media.player
                Repeater {
                  model: ["previous", "toggle", "next"]
                  Item {
                    id: transport
                    required property string modelData
                    width: 42; height: 38
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: transport.modelData === "previous" ? qsTr("Previous track")
                      : transport.modelData === "next" ? qsTr("Next track")
                      : media.player && media.player.isPlaying ? qsTr("Pause") : qsTr("Play")
                    Text {
                      anchors.centerIn: parent
                      text: transport.modelData === "previous" ? "⏮"
                        : transport.modelData === "next" ? "⏭"
                        : media.player && media.player.isPlaying ? "Ⅱ" : "▶"
                      textFormat: Text.PlainText
                      color: "#fafafa"
                      font.pixelSize: transport.modelData === "toggle" ? 25 : 18
                    }
                    TapHandler {
                      onTapped: {
                        if (!media.player) return
                        if (transport.modelData === "previous") media.player.previous()
                        else if (transport.modelData === "next") media.player.next()
                        else media.player.togglePlaying()
                      }
                    }
                  }
                }
              }
            }

            // Dictation: the only state-changing control, and only while
            // recording (KTD6). Transcribing and done show text with no action.
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "dictation"
              Text {
                anchors.centerIn: parent
                width: parent.width - 44
                horizontalAlignment: Text.AlignHCenter
                text: win.selected !== null ? win.selected.text : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: "#f8f8f8"
                font.family: root.fontFamily
                font.pixelSize: 14
              }
              Rectangle {
                readonly property string act: win.selected !== null ? Island.action("dictation", dictation.state) : null
                anchors.horizontalCenter: parent.horizontalCenter
                y: 120
                width: 96; height: 32; radius: 16
                visible: act === "stop"
                color: "#2a2a2a"
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Stop dictation")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Stop")
                  textFormat: Text.PlainText
                  color: "#f2f2f2"
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: dictation.toggle() }
              }
            }

            // Agents: a route to herdr. Rendered only when agents are on.
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "agents"
              Text {
                anchors.centerIn: parent
                width: parent.width - 44
                horizontalAlignment: Text.AlignHCenter
                text: win.selected !== null ? win.selected.text : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: "#f8f8f8"
                font.family: root.fontFamily
                font.pixelSize: 14
              }
              Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 120
                width: 96; height: 32; radius: 16
                color: "#2a2a2a"
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Open herdr")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Herdr")
                  textFormat: Text.PlainText
                  color: "#f2f2f2"
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: agents.openApp() }
              }
            }

            // Messages: a route to Blip. Read-only; never sends (KTD7).
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "messages"
              Text {
                anchors.centerIn: parent
                width: parent.width - 44
                horizontalAlignment: Text.AlignHCenter
                text: win.selected !== null ? win.selected.text : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: "#f8f8f8"
                font.family: root.fontFamily
                font.pixelSize: 14
              }
              Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 120
                width: 96; height: 32; radius: 16
                color: "#2a2a2a"
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Open Blip")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Blip")
                  textFormat: Text.PlainText
                  color: "#f2f2f2"
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: messagesAct.openBlip() }
              }
            }

            // Screenshots: a route to the library.
            Item {
              anchors.fill: parent
              visible: win.selected !== null && win.selected.id === "screenshots"
              Text {
                anchors.centerIn: parent
                width: parent.width - 44
                horizontalAlignment: Text.AlignHCenter
                text: win.selected !== null ? win.selected.text : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: "#f8f8f8"
                font.family: root.fontFamily
                font.pixelSize: 14
              }
              Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 120
                width: 96; height: 32; radius: 16
                color: "#2a2a2a"
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("Open screenshot library")
                Text {
                  anchors.centerIn: parent
                  text: qsTr("Library")
                  textFormat: Text.PlainText
                  color: "#f2f2f2"
                  font.family: root.fontFamily
                  font.pixelSize: 13
                  font.weight: Font.DemiBold
                }
                TapHandler { onTapped: shots.openLibrary() }
              }
            }
          }

          // Dashboard route (R6, KTD8): a deliberate, always-present control.
          Item {
            anchors.right: parent.right
            anchors.rightMargin: 24
            y: 17
            width: 24; height: 24
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Open the dashboard")
            Text {
              anchors.centerIn: parent
              text: "☰"
              textFormat: Text.PlainText
              color: "#8f8f8f"
              font.pixelSize: 16
            }
            TapHandler { onTapped: root.openDashboard() }
          }

          // Close control.
          Item {
            anchors.right: parent.right
            anchors.rightMargin: 24
            y: 132
            width: 24; height: 24
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Close")
            Text {
              anchors.centerIn: parent
              text: "×"
              textFormat: Text.PlainText
              color: "#8f8f8f"
              font.pixelSize: 21
            }
            TapHandler { onTapped: win.closeIsland() }
          }
        }
      }
    }
  }
}
